from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Boolean, BigInteger, DECIMAL, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    status = Column(Enum('draft','training','ready','error'), default='draft')
    file_count = Column(Integer, default=0)
    trained_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    files = relationship("TemplateFile", back_populates="template", cascade="all, delete-orphan")

class TemplateFile(Base):
    __tablename__ = "template_files"
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    file_name = Column(String(500), nullable=False)
    original_name = Column(String(500), nullable=False)
    file_type = Column(Enum('image','video'), nullable=False)
    file_path = Column(String(1000))
    file_url = Column(String(1000))
    file_size_bytes = Column(BigInteger)
    mime_type = Column(String(100))
    llm_summary = Column(Text)
    visual_elements = Column(JSON)
    color_palette = Column(JSON)
    detected_text = Column(Text)
    embedding = Column(JSON)
    phash = Column(String(64))
    processing_status = Column(Enum('pending','processing','done','error'), default='pending')
    processing_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    template = relationship("Template", back_populates="files")

class Validation(Base):
    __tablename__ = "validations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    input_type = Column(Enum('upload','url'), nullable=False)
    input_file_name = Column(String(500))
    input_file_path = Column(String(1000))
    input_url = Column(String(2000))
    input_file_type = Column(Enum('image','video'), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    template_name = Column(String(255), nullable=False)
    post_timestamp = Column(DateTime, nullable=True)
    post_description = Column(Text)
    post_platform = Column(String(100))
    overall_verdict = Column(Enum('appropriate','escalate','need_review'), default='need_review')
    mcc_compliant = Column(Boolean, nullable=True)
    validation_status = Column(Enum('pending','processing','completed','error'), default='pending')
    error_message = Column(Text)
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    template = relationship("Template")
    matches = relationship("ValidationMatch", back_populates="validation", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="validation", uselist=False)

class ValidationMatch(Base):
    __tablename__ = "validation_matches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    validation_id = Column(Integer, ForeignKey("validations.id"), nullable=False)
    template_file_id = Column(Integer, ForeignKey("template_files.id"), nullable=False)
    template_file_name = Column(String(500), nullable=False)
    llm_similarity_score = Column(DECIMAL(5,2), default=0)
    pixel_similarity_score = Column(DECIMAL(5,2), default=0)
    semantic_similarity_score = Column(DECIMAL(5,2), default=0)
    overall_similarity_score = Column(DECIMAL(5,2), default=0)
    is_suspected_match = Column(Boolean, default=False)
    is_exact_pixel_match = Column(Boolean, default=False)
    match_reasoning = Column(Text)
    visual_differences = Column(Text)
    matched_elements = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    validation = relationship("Validation", back_populates="matches")
    template_file = relationship("TemplateFile")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    validation_id = Column(Integer, ForeignKey("validations.id"), unique=True)
    report_ref = Column(String(50), unique=True)
    template_name = Column(String(255))
    input_source = Column(String(500))
    total_files_compared = Column(Integer, default=0)
    suspected_matches = Column(Integer, default=0)
    exact_matches = Column(Integer, default=0)
    overall_verdict = Column(String(50))
    mcc_compliant = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    validation = relationship("Validation", back_populates="report")
