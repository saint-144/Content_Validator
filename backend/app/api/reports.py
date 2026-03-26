from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date
from typing import Optional, List
from datetime import datetime, timedelta
import io

from app.models.database import get_db
from app.models.models import Report, Validation, ValidationMatch, Template, TemplateFile, User
from app.schemas.schemas import ReportOut, DashboardStats
from app.services.export_service import export_validations_to_excel
from app.api.deps import get_current_user, get_current_admin_user

reports_router = APIRouter(prefix="/api/reports", tags=["Reports"])
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@reports_router.get("", response_model=List[ReportOut])
def list_reports(
    template_id: Optional[int] = None,
    verdict: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Report).join(Validation)
    if template_id:
        q = q.filter(Validation.template_id == template_id)
    if verdict:
        q = q.filter(Report.overall_verdict == verdict)
    if from_date:
        q = q.filter(Report.created_at >= datetime.fromisoformat(from_date))
    if to_date:
        q = q.filter(Report.created_at <= datetime.fromisoformat(to_date))
    return q.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


@reports_router.get("/export")
def export_reports(
    template_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export all validation reports to Excel."""
    q = db.query(Validation).options(
        joinedload(Validation.matches),
        joinedload(Validation.report)
    ).filter(Validation.validation_status == "completed")

    if template_id:
        q = q.filter(Validation.template_id == template_id)
    if from_date:
        q = q.filter(Validation.created_at >= datetime.fromisoformat(from_date))
    if to_date:
        q = q.filter(Validation.created_at <= datetime.fromisoformat(to_date))

    validations = q.order_by(Validation.created_at.desc()).all()

    # Build export data
    export_data = []
    for v in validations:
        export_data.append({
            "report_ref": v.report.report_ref if v.report else f"V-{v.id}",
            "template_name": v.template_name,
            "post_timestamp": str(v.post_timestamp or ""),
            "post_description": v.post_description or "",
            "overall_verdict": v.overall_verdict or "need_review",
            "mcc_compliant": v.mcc_compliant,
            "created_at": str(v.created_at),
            "post_url": v.input_url,
            "matches": [
                {
                    "template_file_name": m.template_file_name,
                    "llm_similarity_score": float(m.llm_similarity_score),
                    "pixel_similarity_score": float(m.pixel_similarity_score),
                    "overall_similarity_score": float(m.overall_similarity_score),
                    "is_suspected_match": m.is_suspected_match,
                    "is_exact_pixel_match": m.is_exact_pixel_match,
                    "match_reasoning": m.match_reasoning or ""
                }
                for m in v.matches
            ]
        })

    xlsx_bytes = export_validations_to_excel(export_data)
    filename = f"validation_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@reports_router.get("/{report_id}/detail")
def get_report_detail(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")

    validation = db.query(Validation).options(
        joinedload(Validation.matches)
    ).filter(Validation.id == report.validation_id).first()

    if not validation:
        from fastapi import HTTPException
        raise HTTPException(404, "Validation not found")

    return {
        "report": {
            "id": report.id,
            "report_ref": report.report_ref,
            "template_name": report.template_name,
            "input_source": report.input_source,
            "total_files_compared": report.total_files_compared,
            "suspected_matches": report.suspected_matches,
            "exact_matches": report.exact_matches,
            "overall_verdict": report.overall_verdict,
            "mcc_compliant": report.mcc_compliant,
            "created_at": str(report.created_at)
        },
        "validation": {
            "id": validation.id,
            "input_type": validation.input_type,
            "input_file_name": validation.input_file_name,
            "input_url": validation.input_url,
            "template_name": validation.template_name,
            "post_timestamp": str(validation.post_timestamp or ""),
            "post_description": validation.post_description,
            "post_platform": validation.post_platform,
            "overall_verdict": validation.overall_verdict,
            "mcc_compliant": validation.mcc_compliant,
            "processing_time_ms": validation.processing_time_ms,
            "created_at": str(validation.created_at)
        },
        "matches": [
            {
                "template_file_name": m.template_file_name,
                "llm_similarity_score": float(m.llm_similarity_score),
                "pixel_similarity_score": float(m.pixel_similarity_score),
                "overall_similarity_score": float(m.overall_similarity_score),
                "is_suspected_match": m.is_suspected_match,
                "is_exact_pixel_match": m.is_exact_pixel_match,
                "match_reasoning": m.match_reasoning,
                "visual_differences": m.visual_differences,
                "matched_elements": m.matched_elements
            }
            for m in sorted(validation.matches, key=lambda x: float(x.overall_similarity_score), reverse=True)
        ]
    }


@dashboard_router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = datetime.utcnow().date()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    total_templates = db.query(func.count(Template.id)).scalar() or 0
    total_files = db.query(func.count(TemplateFile.id)).filter(TemplateFile.processing_status == "done").scalar() or 0
    total_validations = db.query(func.count(Validation.id)).filter(Validation.validation_status == "completed").scalar() or 0
    validations_today = db.query(func.count(Validation.id)).filter(
        func.date(Validation.created_at) == today,
        Validation.validation_status == "completed"
    ).scalar() or 0

    appropriate = db.query(func.count(Validation.id)).filter(Validation.overall_verdict == "appropriate").scalar() or 0
    escalate = db.query(func.count(Validation.id)).filter(Validation.overall_verdict == "escalate").scalar() or 0
    need_review = db.query(func.count(Validation.id)).filter(Validation.overall_verdict == "need_review").scalar() or 0
    mcc_yes = db.query(func.count(Validation.id)).filter(Validation.mcc_compliant == True).scalar() or 0
    mcc_no = db.query(func.count(Validation.id)).filter(Validation.mcc_compliant == False).scalar() or 0

    # Top templates by validation count
    top_templates = db.query(
        Validation.template_name,
        func.count(Validation.id).label("count")
    ).group_by(Validation.template_name).order_by(func.count(Validation.id).desc()).limit(5).all()

    # Recent validations
    recent = db.query(Validation).filter(
        Validation.validation_status == "completed"
    ).order_by(Validation.created_at.desc()).limit(10).all()

    # Verdicts by day (last 30 days)
    verdicts_raw = db.query(
        cast(Validation.created_at, Date).label("day"),
        Validation.overall_verdict,
        func.count(Validation.id).label("cnt")
    ).filter(
        Validation.created_at >= thirty_days_ago,
        Validation.validation_status == "completed"
    ).group_by("day", Validation.overall_verdict).all()

    # Platform breakdown
    platform_raw = db.query(
        Validation.post_platform,
        func.count(Validation.id).label("cnt")
    ).filter(
        Validation.post_platform.isnot(None),
        Validation.post_platform != ""
    ).group_by(Validation.post_platform).all()

    return {
        "total_templates": total_templates,
        "total_trained_files": total_files,
        "total_validations": total_validations,
        "validations_today": validations_today,
        "appropriate_count": appropriate,
        "escalate_count": escalate,
        "need_review_count": need_review,
        "mcc_compliant_count": mcc_yes,
        "mcc_non_compliant_count": mcc_no,
        "top_templates": [{"name": r.template_name, "count": r.count} for r in top_templates],
        "recent_validations": [
            {
                "id": v.id,
                "template_name": v.template_name,
                "input_file_name": v.input_file_name or "URL",
                "verdict": v.overall_verdict,
                "mcc_compliant": v.mcc_compliant,
                "created_at": str(v.created_at)
            }
            for v in recent
        ],
        "verdicts_by_day": [
            {"day": str(r.day), "verdict": r.overall_verdict, "count": r.cnt}
            for r in verdicts_raw
        ],
        "platform_breakdown": [
            {"platform": r.post_platform or "Unknown", "count": r.cnt}
            for r in platform_raw
        ]
    }
