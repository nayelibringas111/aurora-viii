from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, issue_local_token
from app.core.config import get_settings
from app.core.db import get_db
from app.models import User
from app.schemas import LocalLogin

router = APIRouter(tags=["auth"])
settings = get_settings()


@router.get("/auth/config")
def auth_config():
    """Público: el frontend decide si mostrar Supabase Auth o el acceso local de desarrollo."""
    return {"auth_mode": settings.auth_mode, "app_name": settings.app_name, "environment": settings.environment}


@router.post("/auth/local-login")
def local_login(body: LocalLogin, db: Session = Depends(get_db)):
    if settings.auth_mode != "local" or (settings.environment == "prod" and not settings.allow_local_auth_in_prod):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No disponible")
    email = body.email.lower()
    existing = db.scalar(select(User).where(User.auth_subject == f"local:{email}"))
    subject = existing.auth_subject if existing else f"local:{email}"
    return {"access_token": issue_local_token(subject, email, body.display_name), "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name, "is_admin": user.is_admin,
            "status": user.status}
