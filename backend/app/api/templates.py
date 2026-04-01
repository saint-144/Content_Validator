from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio

from app.models.database import get_db
from app.models.models import Template, TemplateFile
from app.schemas.schemas import TemplateCreate, TemplateOut, TemplateListOut, TemplateFileOut
from app.services.image_service import save_upload, get_file_type
from app.services.validation_service import train_template_file
from app.config import settings
from app.api.deps import get_current_admin_user, CurrentUser

router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("", response_model=List[TemplateListOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(Template).order_by(Template.created_at.desc()).all()


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_admin_user)):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.post("", response_model=TemplateListOut)
def create_template(data: TemplateCreate, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_admin_user)):
    existing = db.query(Template).filter(Template.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Template '{data.name}' already exists")
    t = Template(name=data.name, description=data.description)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.post("/{template_id}/files")
async def upload_template_files(
    template_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_admin_user)
):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")

    uploaded = []
    for file in files:
        if file.size and file.size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"{file.filename} exceeds {settings.MAX_FILE_SIZE_MB}MB limit")

        try:
            file_type = get_file_type(file.filename or "unknown.jpg")
        except ValueError as e:
            raise HTTPException(400, str(e))

        content = await file.read()
        file_path, saved_name = save_upload(content, file.filename or "upload", f"templates/{template_id}")

        tf = TemplateFile(
            template_id=template_id,
            file_name=saved_name,
            original_name=file.filename or saved_name,
            file_type=file_type,
            file_path=file_path,
            file_size_bytes=len(content),
            mime_type=file.content_type,
            processing_status="pending"
        )
        db.add(tf)
        db.commit()
        db.refresh(tf)

        template.file_count = db.query(TemplateFile).filter(TemplateFile.template_id == template_id).count()
        template.status = "training"
        db.commit()

        asyncio.create_task(_train_file_background(tf.id))
        uploaded.append({"id": tf.id, "file_name": file.filename, "status": "training_started"})

    return {"uploaded": len(uploaded), "files": uploaded, "message": "Files uploaded and parallel training started"}


# Bumped to 5 — safe ceiling for NIM free tier at 40 RPM
training_semaphore = asyncio.Semaphore(5)


async def _train_file_background(template_file_id: int):
    """Background task to train a single template file with retry logic and concurrency control."""
    async with training_semaphore:
        print(f"DEBUG: Starting background training for file ID: {template_file_id}")
        from app.models.database import SessionLocal

        max_retries = 3
        retry_count = 0
        last_error = ""

        while retry_count < max_retries:
            db = SessionLocal()
            try:
                print(f"DEBUG: Attempt {retry_count+1} for file {template_file_id}")
                await train_template_file(db, template_file_id)

                tf = db.query(TemplateFile).filter(TemplateFile.id == template_file_id).first()
                if tf and tf.processing_status == "done":
                    print(f"DEBUG: Successfully trained file {template_file_id} on attempt {retry_count+1}")
                    return
                else:
                    last_error = tf.processing_error if tf else "Unknown error"
                    print(f"DEBUG: File {template_file_id} in error state: {last_error}")

            except Exception as e:
                last_error = str(e)
                print(f"DEBUG: Training attempt {retry_count+1} failed for file {template_file_id}: {e}")
            finally:
                db.close()

            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                print(f"DEBUG: Waiting {wait_time}s before retry {retry_count+1}")
                await asyncio.sleep(wait_time)

        print(f"DEBUG: ALL RETRIES FAILED for file {template_file_id}. Final error: {last_error}")
        db = SessionLocal()
        try:
            tf = db.query(TemplateFile).filter(TemplateFile.id == template_file_id).first()
            if tf:
                tf.processing_status = "error"
                tf.processing_error = f"Failed after {max_retries} attempts. Last error: {last_error}"
                from app.services.validation_service import update_template_status
                await update_template_status(db, tf.template_id)
            db.commit()
        finally:
            db.close()


@router.post("/{template_id}/train")
async def retrain_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_admin_user)
):
    """Retrain all files in a template."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")

    files = db.query(TemplateFile).filter(TemplateFile.template_id == template_id).all()
    if not files:
        raise HTTPException(400, "No files in this template")

    template.status = "training"
    for tf in files:
        tf.processing_status = "pending"
    db.commit()

    for tf in files:
        asyncio.create_task(_train_file_background(tf.id))

    return {"message": f"Retraining {len(files)} files started in parallel", "template_id": template_id}


@router.post("/{template_id}/resume")
async def resume_training(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_admin_user)
):
    """
    Resume training for any files that are pending or stuck in processing.
    - pending: never started or queued but not picked up
    - processing: stuck mid-flight (e.g. container restart, deleted file mid-train)
    Resets stuck processing files back to pending and kicks off training for all.
    """
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")

    # Find all files that need training
    stuck_files = db.query(TemplateFile).filter(
        TemplateFile.template_id == template_id,
        TemplateFile.processing_status == "processing"
    ).all()

    pending_files = db.query(TemplateFile).filter(
        TemplateFile.template_id == template_id,
        TemplateFile.processing_status == "pending"
    ).all()

    if not stuck_files and not pending_files:
        return {
            "message": "No pending or stuck files found — nothing to resume",
            "template_id": template_id,
            "queued": 0
        }

    # Reset stuck files back to pending
    for tf in stuck_files:
        tf.processing_status = "pending"
        tf.processing_error = None

    template.status = "training"
    db.commit()

    # Queue all pending + previously stuck files
    all_to_train = pending_files + stuck_files
    for tf in all_to_train:
        asyncio.create_task(_train_file_background(tf.id))

    return {
        "message": f"Resumed training for {len(all_to_train)} files ({len(stuck_files)} unstuck, {len(pending_files)} pending)",
        "template_id": template_id,
        "queued": len(all_to_train),
        "unstuck": len(stuck_files),
        "pending": len(pending_files)
    }


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_admin_user)):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    return {"message": "Deleted"}


@router.delete("/{template_id}/files/{file_id}")
def delete_template_file(template_id: int, file_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_admin_user)):
    tf = db.query(TemplateFile).filter(
        TemplateFile.id == file_id,
        TemplateFile.template_id == template_id
    ).first()
    if not tf:
        raise HTTPException(404, "File not found")
    db.delete(tf)
    template = db.query(Template).filter(Template.id == template_id).first()
    if template:
        template.file_count = db.query(TemplateFile).filter(TemplateFile.template_id == template_id).count() - 1
    db.commit()
    return {"message": "File deleted"}


@router.post("/{template_id}/sync")
async def sync_template_status(template_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_admin_user)):
    """Manually re-calculate and sync template status."""
    from app.services.validation_service import update_template_status
    new_status = await update_template_status(db, template_id)
    return {"message": "Template status synced", "status": new_status, "template_id": template_id}