"""
Validation Service
Orchestrates the full validation pipeline:
1. Load trained template files
2. Pre-filter to top 30 by phash similarity (fast, no LLM cost)
3. Call LLM for semantic comparison on top 30 only
4. Compute pixel similarity
5. Combine scores and determine verdict
6. Persist results and create report
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.models import Validation, ValidationMatch, TemplateFile, Template, Report
from app.services.llm_service import compare_content, analyze_from_url
from app.services.image_service import (
    compute_phash, phash_similarity, pixel_similarity,
    save_upload, get_file_type, extract_video_thumbnail,
    extract_video_hash_sequence, video_similarity_dtw, cleanup_temp_file
)
from app.config import settings

logger = logging.getLogger(__name__)

# Top N files to send to LLM after phash pre-filter
PHASH_PREFILTER_TOP_N = 30


def _phash_prefilter(
    trained_files: list,
    dest_phash: Optional[str],
    dest_video_sequence: Optional[list],
    dest_type: str,
    top_n: int = PHASH_PREFILTER_TOP_N
) -> tuple[list, dict]:
    """
    Pre-filter trained files by phash/DTW similarity before sending to LLM.
    Returns:
        - top_n files sorted by phash score descending
        - dict of {tf.id: phash_score} for all files (used later to skip recompute)
    """
    scored = []

    for tf in trained_files:
        score = 0.0

        if dest_type == "video" and tf.file_type == "video":
            if dest_video_sequence and tf.embedding and isinstance(tf.embedding, list):
                score = video_similarity_dtw(dest_video_sequence, tf.embedding)
            elif dest_phash and tf.phash:
                score = phash_similarity(dest_phash, tf.phash)

        elif dest_type == "video" and tf.file_type == "image":
            if dest_video_sequence and tf.phash:
                score = video_similarity_dtw(dest_video_sequence, [tf.phash])
            elif dest_phash and tf.phash:
                score = phash_similarity(dest_phash, tf.phash)

        elif dest_type == "image" and tf.file_type == "video":
            if dest_phash and tf.embedding and isinstance(tf.embedding, list):
                score = video_similarity_dtw([dest_phash], tf.embedding)
            elif dest_phash and tf.phash:
                score = phash_similarity(dest_phash, tf.phash)

        elif dest_type == "image" and tf.file_type == "image":
            if dest_phash and tf.phash:
                score = phash_similarity(dest_phash, tf.phash)

        scored.append((tf, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    total = len(scored)
    top = scored[:top_n]
    dropped = total - len(top)

    if dropped > 0:
        logger.info(
            "phash pre-filter: %d total files, sending top %d to LLM, dropped %d "
            "(lowest phash scores: %.1f - %.1f)",
            total, len(top), dropped,
            scored[top_n][1] if top_n < total else 0,
            scored[-1][1]
        )

    phash_scores = {tf.id: score for tf, score in scored}
    top_files = [tf for tf, _ in top]
    return top_files, phash_scores


async def run_validation(db: Session, validation_id: int):
    """Main async validation pipeline. Called after validation record is created."""
    validation = db.query(Validation).filter(Validation.id == validation_id).first()
    if not validation:
        return

    start_time = time.time()
    validation.validation_status = "processing"
    db.commit()

    try:
        # 1. Load template with all trained files
        template = db.query(Template).filter(Template.id == validation.template_id).first()
        if not template:
            raise ValueError(f"Template {validation.template_id} not found")

        trained_files = db.query(TemplateFile).filter(
            TemplateFile.template_id == template.id,
            TemplateFile.processing_status == "done"
        ).all()

        if not trained_files:
            raise ValueError("Template has no trained files yet. Please train the template first.")

        logger.info(
            "Validation %d: template '%s' has %d trained files",
            validation_id, template.name, len(trained_files)
        )

        # 2. Get destination file path
        dest_path = validation.input_file_path
        dest_type = validation.input_file_type
        temp_file = None

        if validation.input_type == "url":
            dest_path, dest_type = await analyze_from_url(validation.input_url)
            temp_file = dest_path

        # 3. Compute pHash / video sequence for destination
        dest_phash = None
        dest_analysis_path = dest_path
        dest_video_sequence = None

        if dest_type == "image" and dest_path:
            dest_phash = compute_phash(dest_path)

        elif dest_type == "video" and dest_path:
            thumb = extract_video_thumbnail(dest_path)
            if thumb:
                dest_analysis_path = thumb
                dest_phash = compute_phash(thumb)
            dest_video_sequence = extract_video_hash_sequence(dest_path)

        # 4. phash pre-filter — fast, no LLM cost
        # Scores ALL files, returns top 30 for LLM + full score map for later use
        top_files, phash_score_map = _phash_prefilter(
            trained_files=trained_files,
            dest_phash=dest_phash,
            dest_video_sequence=dest_video_sequence,
            dest_type=dest_type,
            top_n=PHASH_PREFILTER_TOP_N
        )

        # 5. Build template context for LLM (top 30 only)
        template_context = [
            {
                "id": tf.id,
                "file_name": tf.original_name,
                "llm_summary": tf.llm_summary or "",
                "visual_elements": tf.visual_elements or [],
                "detected_text": tf.detected_text or "",
                "brand_elements": (tf.visual_elements or {}).get("brand_elements", []) if isinstance(tf.visual_elements, dict) else [],
                "phash": tf.phash or ""
            }
            for tf in top_files
        ]

        # 6. Call LLM for semantic comparison on top 30 only
        llm_result = await compare_content(
            destination_path=dest_analysis_path,
            destination_type=dest_type,
            template_files=template_context,
            template_name=template.name,
            pixel_threshold=settings.PIXEL_MATCH_THRESHOLD,
            semantic_threshold=settings.SEMANTIC_MATCH_THRESHOLD
        )

        # 7. Update validation metadata from LLM
        if llm_result.get("post_timestamp_hint"):
            try:
                from dateutil.parser import parse as parse_date
                validation.post_timestamp = parse_date(str(llm_result["post_timestamp_hint"]))
            except Exception:
                pass

        validation.post_description = llm_result.get("destination_description", "")
        validation.post_platform = llm_result.get("platform_hint", "")
        validation.mcc_compliant = llm_result.get("mcc_compliant", True)
        validation.overall_verdict = llm_result.get("overall_verdict", "need_review")

        # 8. Build LLM match lookup
        llm_file_matches = {
            m["file_name"]: m
            for m in llm_result.get("file_matches", [])
            if isinstance(m, dict) and "file_name" in m
        }

        suspected_count = 0
        exact_count = 0

        # 9. Create match records for ALL trained files
        # Top 30 get full LLM + phash scores
        # Remaining files get phash-only scores with no LLM data
        for tf in trained_files:
            prefiltered_phash_score = phash_score_map.get(tf.id, 0.0)
            in_top = tf in top_files

            # 9.1 phash/sequence score — already computed, reuse from map
            phash_score = prefiltered_phash_score

            # 9.2 LLM score — only available for top 30
            llm_match = llm_file_matches.get(tf.original_name, {}) if in_top else {}
            llm_score = float(llm_match.get("llm_similarity_score", 0))
            #is_suspected = bool(llm_match.get("is_suspected_match", llm_score >= settings.SUSPECTED_MATCH_THRESHOLD))
            is_suspected = False  # will be set by our own threshold check in 9.5

            # 9.3 Pixel similarity — only for image-image pairs with high phash
            pixel_score = 0.0
            is_exact_pixel = False

            if dest_type == "image" and tf.file_type == "image":
                if phash_score >= 80 and dest_path and tf.file_path:
                    try:
                        pixel_score = pixel_similarity(dest_path, tf.file_path)
                        is_exact_pixel = pixel_score >= settings.PIXEL_MATCH_THRESHOLD
                    except Exception:
                        pixel_score = phash_score
                else:
                    pixel_score = phash_score
            else:
                pixel_score = phash_score

            # 9.4 Semantic score
            semantic_score = llm_score

            # 9.5 Final weighted score
            if dest_type == "video":
                overall = (float(semantic_score) * 0.25) + (float(phash_score) * 0.75)
                if phash_score >= 95.0:
                    overall = 100.0
                    is_suspected = True
                    is_exact_pixel = True
            else:
                if in_top:
                    if llm_score > 0:
                        # LLM returned a score — full weighted: 60% LLM + 20% phash + 20% pixel
                        overall = (float(semantic_score) * 0.60) + (float(phash_score) * 0.20) + (float(pixel_score) * 0.20)
                    else:
                        # LLM didn't mention this file — it's in top 30 but LLM found no similarity
                        # Use phash + pixel only, no LLM penalty
                        overall = (float(phash_score) * 0.50) + (float(pixel_score) * 0.50)
                else:
                    # Not in top 30 — phash only
                    overall = phash_score

            overall = float(min(100.0, overall))

            if is_suspected or overall >= settings.SUSPECTED_MATCH_THRESHOLD:
                is_suspected = True
                suspected_count += 1
            if is_exact_pixel:
                exact_count += 1

            logger.info(
                "Match [%s] Type=[%s] InTop=%s: Semantic=%.1f, phash=%.1f, Pixel=%.1f -> Overall=%.1f (Suspected=%s, Exact=%s)",
                tf.original_name, dest_type, in_top,
                semantic_score, phash_score, pixel_score,
                overall, is_suspected, is_exact_pixel
            )

            match = ValidationMatch(
                validation_id=validation.id,
                template_file_id=tf.id,
                template_file_name=tf.original_name,
                llm_similarity_score=round(llm_score, 2),
                pixel_similarity_score=round(pixel_score, 2),
                phash_similarity_score=round(phash_score, 2),
                semantic_similarity_score=round(semantic_score, 2),
                overall_similarity_score=round(overall, 2),
                is_suspected_match=is_suspected,
                is_exact_pixel_match=is_exact_pixel,
                match_reasoning=llm_match.get("match_reasoning", "") if in_top else "Not in top 30 phash candidates — phash score only",
                visual_differences=llm_match.get("visual_differences", "") if in_top else "",
                matched_elements=llm_match.get("matched_elements", []) if in_top else []
            )
            db.add(match)

        # 10. Override verdict based on match findings
        if exact_count > 0:
            validation.overall_verdict = "appropriate"
            validation.mcc_compliant = True
        elif suspected_count > 0:
            validation.overall_verdict = "need_review"
        else:
            validation.overall_verdict = "escalate"
            validation.mcc_compliant = False
            validation.error_message = "No matching approved template found for this content."

        # Final rule: if LLM explicitly found MCC issues, override to escalate
        if llm_result.get("mcc_compliant") is False:
            validation.overall_verdict = "escalate"
            validation.mcc_compliant = False

        # 11. Complete validation
        elapsed_ms = int((time.time() - start_time) * 1000)
        validation.validation_status = "completed"
        validation.completed_at = datetime.utcnow()
        validation.processing_time_ms = elapsed_ms
        db.commit()

        # 12. Create report record
        report_ref = f"RPT-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        report = Report(
            validation_id=validation.id,
            report_ref=report_ref,
            template_name=template.name,
            input_source=validation.input_file_name or validation.input_url or "",
            total_files_compared=len(trained_files),
            suspected_matches=suspected_count,
            exact_matches=exact_count,
            overall_verdict=validation.overall_verdict,
            mcc_compliant=validation.mcc_compliant,
            created_by=validation.created_by
        )
        db.add(report)
        db.commit()

        # Cleanup temp files
        if temp_file:
            cleanup_temp_file(temp_file)
        if dest_analysis_path and dest_analysis_path != dest_path:
            cleanup_temp_file(dest_analysis_path)

        logger.info(
            "Validation %d completed in %dms: %s (files: %d total, %d to LLM, %d suspected, %d exact)",
            validation.id, elapsed_ms, validation.overall_verdict,
            len(trained_files), len(top_files), suspected_count, exact_count
        )

    except Exception as e:
        logger.error("Validation %d failed: %s", validation_id, e, exc_info=True)
        validation.validation_status = "error"
        validation.error_message = str(e)
        validation.processing_time_ms = int((time.time() - start_time) * 1000)
        db.commit()


async def update_template_status(db: Session, template_id: int) -> str:
    """Re-calculate and update the overall status of a template based on its files."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        return "error"

    all_files = db.query(TemplateFile).filter(TemplateFile.template_id == template_id).all()
    total_count = len(all_files)
    done_count = sum(1 for f in all_files if f.processing_status == "done")
    error_count = sum(1 for f in all_files if f.processing_status == "error")
    working_count = sum(1 for f in all_files if f.processing_status in ["pending", "processing"])

    template.file_count = total_count

    if total_count == 0:
        template.status = "draft"
    elif working_count == 0:
        if done_count > 0:
            template.status = "ready"
            template.trained_at = datetime.utcnow()
        else:
            template.status = "error"
    else:
        template.status = "training"

    db.commit()
    logger.info(
        "Template %d status updated to %s (Done: %d, Working: %d, Error: %d)",
        template_id, template.status, done_count, working_count, error_count
    )
    return template.status


async def train_template_file(db: Session, template_file_id: int):
    """Process a single template file: compute hashes and call LLM for analysis."""
    from app.services.llm_service import analyze_content_for_training

    tf = db.query(TemplateFile).filter(TemplateFile.id == template_file_id).first()
    if not tf:
        return

    tf.processing_status = "processing"
    db.commit()

    file_path = None
    analysis_path = None

    try:
        file_path = tf.file_path or tf.file_url
        analysis_path = file_path

        if tf.file_type == "video" and tf.file_path:
            thumb = extract_video_thumbnail(tf.file_path)
            if thumb:
                analysis_path = thumb

        if tf.file_type == "image" and tf.file_path:
            tf.phash = compute_phash(tf.file_path)

        if tf.file_type == "video" and tf.file_path:
            tf.phash = compute_phash(analysis_path)
            tf.embedding = extract_video_hash_sequence(tf.file_path)

        result = await analyze_content_for_training(
            file_path=analysis_path or "",
            file_type=tf.file_type,
            file_name=tf.original_name
        )

        tf.llm_summary = str(result.get("summary", ""))
        tf.visual_elements = result
        tf.detected_text = str(result.get("detected_text", ""))
        tf.color_palette = result.get("color_palette", [])
        tf.processing_status = "done"

    except Exception as e:
        logger.error("Training failed for file %d: %s", template_file_id, e)
        tf.processing_status = "error"
        tf.processing_error = str(e)

    finally:
        db.commit()
        await update_template_status(db, tf.template_id)
        if analysis_path and file_path and analysis_path != file_path:
            cleanup_temp_file(analysis_path)