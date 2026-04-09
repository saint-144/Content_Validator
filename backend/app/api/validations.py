from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import io
import asyncio

from app.models.database import get_db
from app.models.models import Validation, ValidationMatch, Template, Report
from app.schemas.schemas import ValidationOut, ValidationCreateURL
from app.services.image_service import save_upload, get_file_type
from app.services.validation_service import run_validation
from app.services.export_service import export_validations_to_excel
from app.config import settings
from app.api.deps import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/validations", tags=["Validations"])

# Concurrency control for validation (Turbo Mode)
validation_semaphore = asyncio.Semaphore(5)


@router.get("", response_model=List[ValidationOut])
def list_validations(
    template_id: Optional[int] = None,
    verdict: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(["admin", "user"]))
):
    q = db.query(Validation)
    if template_id:
        q = q.filter(Validation.template_id == template_id)
    if verdict:
        q = q.filter(Validation.overall_verdict == verdict)
    if status:
        q = q.filter(Validation.validation_status == status)
    return q.order_by(Validation.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


@router.get("/{validation_id}", response_model=ValidationOut)
def get_validation(validation_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_roles(["admin", "user"]))):
    v = db.query(Validation).filter(Validation.id == validation_id).first()
    if not v:
        raise HTTPException(404, "Validation not found")
    return v


@router.post("/upload")
async def validate_upload(
    template_id: int = Form(...),
    post_timestamp: Optional[str] = Form(None),
    post_description: Optional[str] = Form(None),
    post_platform: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(["admin", "user"]))
):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")
    if template.status != "ready":
        raise HTTPException(400, f"Template '{template.name}' is not ready. Status: {template.status}")

    if file.size and file.size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit")

    try:
        file_type = get_file_type(file.filename or "upload.jpg")
    except ValueError as e:
        raise HTTPException(400, str(e))

    content = await file.read()
    file_path, saved_name = save_upload(content, file.filename or "upload", "validations")

    ts = None
    if post_timestamp:
        try:
            ts = datetime.fromisoformat(post_timestamp.replace("Z", "+00:00"))
        except Exception:
            pass

    validation = Validation(
        input_type="upload",
        input_file_name=file.filename or saved_name,
        input_file_path=file_path,
        input_file_type=file_type,
        template_id=template_id,
        template_name=template.name,
        post_timestamp=ts,
        post_description=post_description,
        post_platform=post_platform,
        validation_status="pending",
        created_by=current_user.id
    )
    db.add(validation)
    db.commit()
    db.refresh(validation)

    # Use asyncio.create_task for immediate background execution
    asyncio.create_task(_run_validation_background(validation.id))

    return {"validation_id": validation.id, "status": "processing", "message": "Validation started in parallel"}


@router.post("/url")
async def validate_url(
    data: ValidationCreateURL,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(["admin", "user"]))
):
    template = db.query(Template).filter(Template.id == data.template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")
    if template.status != "ready":
        raise HTTPException(400, f"Template not ready. Status: {template.status}")

    validation = Validation(
        input_type="url",
        input_url=data.url,
        input_file_name=data.url.split("/")[-1][:100] or "url_content",
        input_file_type="image",
        template_id=data.template_id,
        template_name=template.name,
        post_timestamp=data.post_timestamp,
        post_description=data.post_description,
        post_platform=data.post_platform,
        validation_status="pending",
        created_by=current_user.id
    )
    db.add(validation)
    db.commit()
    db.refresh(validation)

    # Use asyncio.create_task for immediate background execution
    asyncio.create_task(_run_validation_background(validation.id))

    return {"validation_id": validation.id, "status": "processing", "message": "Validation started in parallel"}


@router.get("/{validation_id}/status")
def get_validation_status(validation_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_roles(["admin", "user"]))):
    v = db.query(Validation).filter(Validation.id == validation_id).first()
    if not v:
        raise HTTPException(404)
    return {
        "id": v.id,
        "status": v.validation_status,
        "verdict": v.overall_verdict,
        "mcc_compliant": v.mcc_compliant,
        "processing_time_ms": v.processing_time_ms,
        "error": v.error_message
    }


async def _run_validation_background(validation_id: int):
    async with validation_semaphore:
        print(f"DEBUG: Starting background validation for ID: {validation_id}")
        from app.models.database import SessionLocal
        db = SessionLocal()
        try:
            print(f"DEBUG: Session acquired for validation {validation_id}, calling run_validation...")
            await run_validation(db, validation_id)
            print(f"DEBUG: Completed validation for ID: {validation_id}")
        except Exception as e:
            print(f"DEBUG: VALIDATION BACKGROUND ERROR for ID {validation_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
