from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from app.models.database import get_db
from app.core.security import verify_password, create_access_token
from app.api.deps import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str


@router.post("/token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    result = db.execute(
        text("SELECT id, username, password, role FROM users WHERE username = :username"),
        {"username": form_data.username}
    ).fetchone()

    if not result or not verify_password(form_data.password, result[2]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=result[0], role=result[3])
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": result[3]
    }


@router.get("/me", response_model=UserOut)
def read_users_me(current_user: CurrentUser = Depends(require_roles(["admin", "user"]))):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )