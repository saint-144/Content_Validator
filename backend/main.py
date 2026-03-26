from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.models.database import create_tables
from app.api.templates import router as templates_router
from app.api.validations import router as validations_router
from app.api.reports import reports_router, dashboard_router
from app.api.auth import router as auth_router

app = FastAPI(
    title="Content Validation Platform API",
    description="LLM-powered content validation against trained templates",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register routers
app.include_router(auth_router)
app.include_router(templates_router)
app.include_router(validations_router)
app.include_router(reports_router)
app.include_router(dashboard_router)

# Serve uploads as static files
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.on_event("startup")
async def startup():
    create_tables()

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

@app.get("/")
def root():
    return {"message": "Content Validation Platform API", "docs": "/docs"}
