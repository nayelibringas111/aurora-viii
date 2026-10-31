"""Autenticación: valida el JWT y resuelve el usuario de aplicación.

- AUTH_MODE=supabase → tokens de Supabase Auth. Se validan con las claves públicas (JWKS) del proyecto
  o, si está definido, con el secreto HS256 legado (SUPABASE_JWT_SECRET).
- AUTH_MODE=local    → tokens HS256 emitidos por /api/v1/auth/local-login (desarrollo y demos).
"""
import logging
import time
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User

log = logging.getLogger("aurora.auth")
settings = get_settings()
_jwks_client: jwt.PyJWKClient | None = None


def _jwks() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not settings.supabase_url:
            raise RuntimeError("SUPABASE_URL es obligatorio con AUTH_MODE=supabase")
        _jwks_client = jwt.PyJWKClient(f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
                                       cache_keys=True, lifespan=600)  # Supabase cachea el JWKS 10 min
    return _jwks_client


@dataclass
class TokenClaims:
    subject: str
    email: str
    name: str


def issue_local_token(subject: str, email: str, name: str, ttl: int = 12 * 3600) -> str:
    now = int(time.time())
    return jwt.encode({"sub": subject, "email": email, "name": name, "iat": now, "exp": now + ttl,
                       "iss": "aurora-viii-local", "aud": "aurora-viii"}, settings.local_jwt_secret, algorithm="HS256")


def decode_token(token: str) -> TokenClaims:
    try:
        if settings.auth_mode == "local":
            data = jwt.decode(token, settings.local_jwt_secret, algorithms=["HS256"], audience="aurora-viii",
                              issuer="aurora-viii-local")
        else:
            header = jwt.get_unverified_header(token)
            issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None
            if header.get("alg") == "HS256":
                if not settings.supabase_jwt_secret:
                    raise jwt.InvalidTokenError("Token HS256 sin SUPABASE_JWT_SECRET configurado")
                key = settings.supabase_jwt_secret
                algs = ["HS256"]
            else:
                key = _jwks().get_signing_key_from_jwt(token).key
                algs = ["ES256", "RS256", "EdDSA"]
            data = jwt.decode(token, key, algorithms=algs, audience=settings.supabase_jwt_audience, issuer=issuer)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión expirada")
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
        log.info("Token rechazado: %s", exc.__class__.__name__)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")

    email = (data.get("email") or "").lower()
    meta = data.get("user_metadata") or {}
    name = data.get("name") or meta.get("full_name") or meta.get("name") or (email.split("@")[0] if email else "usuario")
    if not data.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sin sujeto")
    return TokenClaims(subject=str(data["sub"]), email=email, name=name)


def _extract_token(request: Request) -> str:
    authz = request.headers.get("Authorization", "")
    if authz.lower().startswith("bearer "):
        return authz[7:].strip()
    # EventSource del navegador no admite cabeceras: aceptamos ?access_token= solo en la ruta de eventos
    if request.url.path.endswith("/events"):
        tok = request.query_params.get("access_token")
        if tok:
            return tok
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticación requerida")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    claims = decode_token(_extract_token(request))
    user = db.scalar(select(User).where(User.auth_subject == claims.subject))
    if user is None:
        first_user = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
        is_admin = claims.email in settings.admin_emails or (first_user and settings.environment != "prod")
        user = User(id=uuid.uuid4(), auth_subject=claims.subject, email=claims.email or f"{claims.subject}@sin-correo",
                    display_name=claims.name[:80], is_admin=is_admin)
        db.add(user)
        db.commit()
        from app.modules.audit import record  # import diferido para evitar ciclos
        record(db, user.id, None, "user.first_login", {"email": user.email, "is_admin": is_admin})
        db.commit()
    elif claims.email in settings.admin_emails and not user.is_admin:
        user.is_admin = True
        db.commit()
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario suspendido")
    request.state.user_id = str(user.id)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere rol Administrador")
    return user
