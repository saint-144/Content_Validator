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

router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("", response_model=List[TemplateListOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(Template).order_by(Template.created_at.desc()).all()


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.post("", response_model=TemplateListOut)
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")

    uploaded = []
    for file in files:
        # Validate
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

        # Queue training in background
        tf_id = tf.id
        background_tasks.add_task(_train_file_background, tf_id)
        uploaded.append({"id": tf.id, "file_name": file.filename, "status": "queued_for_training"})

    return {"uploaded": len(uploaded), "files": uploaded, "message": "Files uploaded and training started"}


async def _train_file_background(template_file_id: int):
    """Background task to train a single template file."""
    from app.models.database import SessionLocal
    db = SessionLocal()
    try:
        await train_template_file(db, template_file_id)
    finally:
        db.close()


@router.post("/{template_id}/train")
async def retrain_template(
    template_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
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
        background_tasks.add_task(_train_file_background, tf.id)

    return {"message": f"Retraining {len(files)} files", "template_id": template_id}


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    return {"message": "Deleted"}


@router.delete("/{template_id}/files/{file_id}")
def delete_template_file(template_id: int, file_id: int, db: Session = Depends(get_db)):
    tf = db.query(TemplateFile).filter(
        TemplateFile.id == file_id,
        TemplateFile.template_id == template_id
    ).first()
    if not tf:
        raise HTTPException(404, "File not found")
    db.delete(tf)
    # Update count
    template = db.query(Template).filter(Template.id == template_id).first()
    if template:
        template.file_count = db.query(TemplateFile).filter(TemplateFile.template_id == template_id).count() - 1
    db.commit()
    return {"message": "File deleted"}
