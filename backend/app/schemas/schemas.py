from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

class TemplateStatus(str, Enum):
    draft = "draft"
    training = "training"
    ready = "ready"
    error = "error"

class ValidationVerdict(str, Enum):
    appropriate = "appropriate"
    escalate = "escalate"
    need_review = "need_review"

# ─── Templates ───────────────────────────────────────────────────────────────
class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None

class TemplateFileOut(BaseModel):
    id: int
    file_name: str
    original_name: str
    file_type: str
    file_size_bytes: Optional[int]
    llm_summary: Optional[str]
    visual_elements: Optional[Any]
    detected_text: Optional[str]
    processing_status: str
    created_at: datetime
    class Config: from_attributes = True

class TemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    file_count: int
    trained_at: Optional[datetime]
    created_at: datetime
    files: List[TemplateFileOut] = []
    class Config: from_attributes = True

class TemplateListOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    file_count: int
    trained_at: Optional[datetime]
    created_at: datetime
    class Config: from_attributes = True

# ─── Validations ─────────────────────────────────────────────────────────────
class ValidationMatchOut(BaseModel):
    id: int
    template_file_id: int
    template_file_name: str
    llm_similarity_score: float
    pixel_similarity_score: float
    semantic_similarity_score: float
    overall_similarity_score: float
    is_suspected_match: bool
    is_exact_pixel_match: bool
    match_reasoning: Optional[str]
    visual_differences: Optional[str]
    matched_elements: Optional[Any]
    class Config: from_attributes = True

class ValidationOut(BaseModel):
    id: int
    input_type: str
    input_file_name: Optional[str]
    input_url: Optional[str]
    input_file_type: str
    template_id: int
    template_name: str
    post_timestamp: Optional[datetime]
    post_description: Optional[str]
    post_platform: Optional[str]
    overall_verdict: Optional[str]
    mcc_compliant: Optional[bool]
    validation_status: str
    processing_time_ms: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    matches: List[ValidationMatchOut] = []
    class Config: from_attributes = True

class ValidationCreateURL(BaseModel):
    url: str
    template_id: int
    post_timestamp: Optional[datetime] = None
    post_description: Optional[str] = None
    post_platform: Optional[str] = None

# ─── Reports ─────────────────────────────────────────────────────────────────
class ReportOut(BaseModel):
    id: int
    validation_id: int
    report_ref: str
    template_name: Optional[str]
    input_source: Optional[str]
    total_files_compared: int
    suspected_matches: int
    exact_matches: int
    overall_verdict: Optional[str]
    mcc_compliant: Optional[bool]
    created_at: datetime
    class Config: from_attributes = True

# ─── Dashboard ───────────────────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_templates: int
    total_trained_files: int
    total_validations: int
    validations_today: int
    appropriate_count: int
    escalate_count: int
    need_review_count: int
    mcc_compliant_count: int
    mcc_non_compliant_count: int
    top_templates: List[dict]
    recent_validations: List[dict]
    verdicts_by_day: List[dict]
    platform_breakdown: List[dict]
