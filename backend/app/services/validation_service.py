"""
Validation Service
Orchestrates the full validation pipeline:
1. Load trained template files
2. Call LLM for semantic comparison
3. Compute pixel similarity
4. Combine scores and determine verdict
5. Persist results and create report
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Validation, ValidationMatch, TemplateFile, Template, Report
from app.services.llm_service import compare_content, analyze_from_url
from app.services.image_service import (
    compute_phash, phash_similarity, pixel_similarity,
    save_upload, get_file_type, extract_video_thumbnail, cleanup_temp_file
)
from app.config import settings

logger = logging.getLogger(__name__)


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

        # 2. Get destination file path
        dest_path = validation.input_file_path
        dest_type = validation.input_file_type
        temp_file = None

        if validation.input_type == "url":
            dest_path, dest_type = await analyze_from_url(validation.input_url)
            temp_file = dest_path

        # 3. Compute pHash for destination
        dest_phash = None
        if dest_type == "image" and dest_path:
            dest_phash = compute_phash(dest_path)

        # For video, extract thumbnail
        dest_analysis_path = dest_path
        if dest_type == "video" and dest_path:
            thumb = extract_video_thumbnail(dest_path)
            if thumb:
                dest_analysis_path = thumb

        # 4. Build template file context for LLM
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
            for tf in trained_files
        ]

        # 5. Call LLM for semantic comparison
        llm_result = await compare_content(
            destination_path=dest_analysis_path,
            destination_type=dest_type,
            template_files=template_context,
            template_name=template.name,
            pixel_threshold=settings.PIXEL_MATCH_THRESHOLD,
            semantic_threshold=settings.SEMANTIC_MATCH_THRESHOLD
        )

        # 6. Update validation metadata from LLM
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

        # 7. Create per-file match records
        llm_file_matches = {
            m["file_name"]: m
            for m in llm_result.get("file_matches", [])
            if isinstance(m, dict) and "file_name" in m
        }

        suspected_count = 0
        exact_count = 0

        for tf in trained_files:
            llm_match = llm_file_matches.get(tf.original_name, {})

            llm_score = float(llm_match.get("llm_similarity_score", 0))
            is_suspected = bool(llm_match.get("is_suspected_match", llm_score >= settings.SUSPECTED_MATCH_THRESHOLD))

            # 7.1. pHash similarity for images (20% of overall)
            phash_score = 0.0
            if dest_type == "image" and tf.file_type == "image" and dest_phash and tf.phash:
                phash_score = phash_similarity(dest_phash, tf.phash)

            # 7.2. Pixel similarity for images (20% of overall)
            pixel_score = 0.0
            is_exact_pixel = False
            if dest_type == "image" and tf.file_type == "image":
                # Compute pixel similarity if phash is decent (optimization)
                if phash_score >= 70 and dest_path and tf.file_path:
                    try:
                        pixel_score = pixel_similarity(dest_path, tf.file_path)
                        is_exact_pixel = pixel_score >= settings.PIXEL_MATCH_THRESHOLD
                    except Exception:
                        pass
                else:
                    # If phash is low, use phash score as fallback for pixel
                    pixel_score = phash_score

            # 7.3. Semantic score from LLM (60% of overall)
            semantic_score = llm_score

            # Weighted overall: 60% Semantic, 20% pHash, 20% Pixel
            overall = (float(semantic_score) * 0.60) + (float(phash_score) * 0.20) + (float(pixel_score) * 0.20)
            overall = float(min(100.0, overall))

            if is_suspected or overall >= settings.SUSPECTED_MATCH_THRESHOLD:
                is_suspected = True
                suspected_count += 1
            if is_exact_pixel:
                exact_count += 1

            logger.info(
                "Match Analysis [%s]: Semantic=%.1f, pHash=%.1f, Pixel=%.1f -> Overall=%.1f (Suspected=%s, Exact=%s)",
                tf.original_name, semantic_score, phash_score, pixel_score, overall, is_suspected, is_exact_pixel
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
                match_reasoning=llm_match.get("match_reasoning", ""),
                visual_differences=llm_match.get("visual_differences", ""),
                matched_elements=llm_match.get("matched_elements", [])
            )
            db.add(match)

        # 8. Override verdict based on match findings
        if exact_count > 0:
            validation.overall_verdict = "appropriate"
            validation.mcc_compliant = True # Matching approved template = Compliant
        elif suspected_count > 0:
            validation.overall_verdict = "need_review"
        else:
            # 0 matches = Not approved content
            validation.overall_verdict = "escalate"
            validation.mcc_compliant = False
            validation.error_message = "No matching approved template found for this content."

        # Final rule: if LLM explicitly found MCC issues, override to escalate
        if llm_result.get("mcc_compliant") is False:
            validation.overall_verdict = "escalate"
            validation.mcc_compliant = False

        # 9. Complete validation
        elapsed_ms = int((time.time() - start_time) * 1000)
        validation.validation_status = "completed"
        validation.completed_at = datetime.utcnow()
        validation.processing_time_ms = elapsed_ms
        db.commit()

        # 10. Create report record
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
            mcc_compliant=validation.mcc_compliant
        )
        db.add(report)
        db.commit()

        # Cleanup temp files
        if temp_file:
            cleanup_temp_file(temp_file)
        if dest_analysis_path and dest_analysis_path != dest_path:
            cleanup_temp_file(dest_analysis_path)

        logger.info("Validation %d completed in %dms: %s", validation.id, elapsed_ms, validation.overall_verdict)

    except Exception as e:
        logger.error("Validation %d failed: %s", validation_id, e, exc_info=True)
        validation.validation_status = "error"
        validation.error_message = str(e)
        validation.processing_time_ms = int((time.time() - start_time) * 1000)
        db.commit()


async def update_template_status(db: Session, template_id: int) -> str:
    """
    Re-calculate and update the overall status of a template based on its files.
    Returns the new status.
    """
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
        # All files finished processing
        if done_count > 0:
            template.status = "ready"
            template.trained_at = datetime.utcnow()
        else:
            template.status = "error"
    else:
        template.status = "training"
    
    db.commit()
    logger.info("Template %d status updated to %s (Done: %d, Working: %d, Error: %d)", 
                template_id, template.status, done_count, working_count, error_count)
    return template.status


async def train_template_file(db: Session, template_file_id: int):
    """Process a single template file: compute hashes and call LLM for analysis."""
    from app.services.llm_service import analyze_content_for_training

    tf = db.query(TemplateFile).filter(TemplateFile.id == template_file_id).first()
    if not tf:
        return

    tf.processing_status = "processing"
    db.commit()

    try:
        file_path = tf.file_path or tf.file_url
        analysis_path = file_path

        # For video, extract thumbnail for analysis
        if tf.file_type == "video" and tf.file_path:
            thumb = extract_video_thumbnail(tf.file_path)
            if thumb:
                analysis_path = thumb

        # Compute pHash for images
        if tf.file_type == "image" and tf.file_path:
            tf.phash = compute_phash(tf.file_path)

        # LLM analysis
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
        # Commit file changes first
        db.commit()
        # Update template status
        await update_template_status(db, tf.template_id)
        
        # Cleanup video thumbnail if it was created
        if 'analysis_path' in locals() and analysis_path and analysis_path != file_path:
            cleanup_temp_file(analysis_path)
