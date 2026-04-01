import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Any, Union
from jose import jwt
from passlib.handlers.django import django_pbkdf2_sha256

SECRET_KEY = "django-insecure-cv-auth-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Django pbkdf2 or legacy bcrypt hash."""
    try:
        if hashed_password.startswith("pbkdf2_sha256$"):
            return django_pbkdf2_sha256.verify(plain_password, hashed_password)
        # Fallback for bcrypt legacy passwords
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt — for legacy use only. New users are created via Django."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "role": role}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)