#!/usr/bin/env python3
"""
seed_demo.py — Insert demo data to explore the platform without running real validations.
Run: python seed_demo.py
Requires the backend .env to be configured and MySQL running.
"""

import sys, os, json, random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/backend")

from app.config import settings
from app.models.database import SessionLocal, create_tables
from app.models.models import Template, TemplateFile, Validation, ValidationMatch, Report

import uuid

TEMPLATES = [
    ("Q1 2024 Instagram Campaign", "Brand campaign creatives for Q1 social posts", 8),
    ("Product Launch — ModelX", "Official product launch visuals for ModelX", 12),
    ("Holiday Season 2024", "Festive campaign images for Dec/Jan", 6),
]

PLATFORMS = ["Instagram", "Facebook", "Twitter/X", "LinkedIn", "TikTok"]
VERDICTS  = ["appropriate", "escalate", "need_review"]
WEIGHTS   = [0.55, 0.20, 0.25]

IMAGE_NAMES = [
    "hero_banner_v1.jpg", "product_shot_main.png", "lifestyle_photo_A.jpg",
    "carousel_slide_1.jpg", "carousel_slide_2.jpg", "story_template.png",
    "reels_cover.jpg", "brand_logo_lockup.png", "campaign_cta_v2.jpg",
    "influencer_collab_1.jpg", "influencer_collab_2.jpg", "feature_highlight.jpg",
]

def seed():
    create_tables()
    db = SessionLocal()
    try:
        # Clear existing demo data
        db.query(Report).delete()
        db.query(ValidationMatch).delete()
        db.query(Validation).delete()
        db.query(TemplateFile).delete()
        db.query(Template).delete()
        db.commit()
        print("Cleared existing data.")

        created_templates = []
        for tname, tdesc, fcount in TEMPLATES:
            t = Template(name=tname, description=tdesc, status="ready",
                         file_count=fcount, trained_at=datetime.utcnow() - timedelta(days=random.randint(1,14)))
            db.add(t); db.flush()

            for i in range(fcount):
                fname = random.choice(IMAGE_NAMES)
                tf = TemplateFile(
                    template_id=t.id,
                    file_name=f"{uuid.uuid4().hex[:8]}_{fname}",
                    original_name=fname,
                    file_type="image",
                    file_size_bytes=random.randint(50_000, 2_000_000),
                    mime_type="image/jpeg",
                    llm_summary=f"Brand creative showing {fname.replace('_',' ').replace('.jpg','').replace('.png','')}. Contains brand logo, product imagery, and campaign messaging with consistent color palette.",
                    visual_elements={"visual_elements": ["brand logo","product image","tagline","CTA button"], "color_palette": ["#1E3A5F","#FFFFFF","#F59E0B"]},
                    detected_text=f"Brand Name | {tname[:20]} | Learn More",
                    phash=f"{random.randint(0, 2**64):016x}",
                    processing_status="done",
                )
                db.add(tf)

            db.commit()
            created_templates.append(t)
            print(f"  Created template: {tname} ({fcount} files)")

        # Create demo validations over the last 30 days
        print("\nCreating demo validations...")
        val_count = 0
        for days_ago in range(30, 0, -1):
            count_today = random.randint(0, 5)
            for _ in range(count_today):
                t = random.choice(created_templates)
                verdict = random.choices(VERDICTS, WEIGHTS)[0]
                platform = random.choice(PLATFORMS)
                post_dt  = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0,23))
                created  = post_dt + timedelta(minutes=random.randint(5,120))
                mcc_ok   = False if verdict == "escalate" else random.random() > 0.08

                fname    = random.choice(IMAGE_NAMES)
                v = Validation(
                    input_type=random.choice(["upload", "url"]),
                    input_file_name=fname,
                    input_file_type="image",
                    template_id=t.id,
                    template_name=t.name,
                    post_timestamp=post_dt,
                    post_description=f"Check out our latest {platform} post! #brand #campaign #new",
                    post_platform=platform,
                    overall_verdict=verdict,
                    mcc_compliant=mcc_ok,
                    validation_status="completed",
                    processing_time_ms=random.randint(8_000, 45_000),
                    created_at=created,
                    completed_at=created + timedelta(seconds=random.randint(20,90))
                )
                db.add(v); db.flush()

                # Matches for this validation
                files = db.query(TemplateFile).filter(TemplateFile.template_id == t.id).all()
                has_match = verdict == "appropriate"
                for tf in files:
                    score   = random.uniform(70, 98) if has_match else random.uniform(15, 65)
                    suspect = score >= 65
                    exact   = score >= 95 and has_match
                    db.add(ValidationMatch(
                        validation_id=v.id,
                        template_file_id=tf.id,
                        template_file_name=tf.original_name,
                        llm_similarity_score=round(score * 0.9, 2),
                        pixel_similarity_score=round(score * 0.85 if exact else score * 0.3, 2),
                        semantic_similarity_score=round(score, 2),
                        overall_similarity_score=round(score * 0.88, 2),
                        is_suspected_match=suspect,
                        is_exact_pixel_match=exact,
                        match_reasoning="Demo match — LLM analysis would appear here in production.",
                    ))

                # Report
                ref = f"RPT-{created.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
                suspected = sum(1 for tf in files if random.random() > 0.6)
                db.add(Report(
                    validation_id=v.id,
                    report_ref=ref,
                    template_name=t.name,
                    input_source=fname,
                    total_files_compared=len(files),
                    suspected_matches=suspected if has_match else 0,
                    exact_matches=1 if has_match and random.random() > 0.4 else 0,
                    overall_verdict=verdict,
                    mcc_compliant=mcc_ok,
                    created_at=created
                ))
                val_count += 1

        db.commit()
        print(f"  Created {val_count} demo validations with matches and reports.")
        print("\n✅ Seed complete! Open http://localhost:8083/dashboard to explore.")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
