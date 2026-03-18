import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "mysql+pymysql://root:Validator@2024@localhost:3306/content_validator"
    
    # LLM Provider: "anthropic", "openai", or "gemini"
    LLM_PROVIDER: str = "gemini"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100
    
    # Matching thresholds
    PIXEL_MATCH_THRESHOLD: float = 95.0
    SEMANTIC_MATCH_THRESHOLD: float = 72.0
    SUSPECTED_MATCH_THRESHOLD: float = 65.0
    
    # App
    APP_NAME: str = "Content Validator"
    DEBUG: bool = True
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:4200", "http://localhost"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# Ensure upload directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(f"{settings.UPLOAD_DIR}/templates", exist_ok=True)
os.makedirs(f"{settings.UPLOAD_DIR}/validations", exist_ok=True)
