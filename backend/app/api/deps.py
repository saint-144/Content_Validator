from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, ValidationError
from typing import Optional

from app.models.database import get_db
from app.core.security import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# Simple user representation since SQLAlchemy no longer owns the users table
class CurrentUser(BaseModel):
    id: int
    username: str
    role: str
    name: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> CurrentUser:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Support both Django-SimpleJWT ('user_id') and FastAPI JWT ('sub')
    user_id = payload.get("user_id") or payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    result = db.execute(
        text("SELECT id, username, role, name, position, email FROM users WHERE id = :id"),
        {"id": int(user_id)}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    return CurrentUser(
        id=result[0],
        username=result[1],
        role=result[2],
        name=result[3],
        position=result[4],
        email=result[5]
    )


def require_roles(allowed_roles: list[str]):
    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    return role_checker


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


# Alias expected by templates.py and other routers
def get_current_admin_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user