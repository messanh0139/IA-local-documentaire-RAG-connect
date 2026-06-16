from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Header, HTTPException, status

from app.core.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str | None,
    display_name: str | None,
    groups: list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "display_name": display_name,
        "groups": groups or ["everyone"],
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    email: str | None
    display_name: str | None
    group_ids: tuple[str, ...]


async def get_current_principal(
    authorization: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_groups: str | None = Header(default=None),
) -> Principal:
    # ── JWT Bearer auth ──────────────────────────────────────────────────────
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return Principal(
                tenant_id=payload["tenant_id"],
                user_id=payload["sub"],
                email=payload.get("email"),
                display_name=payload.get("display_name"),
                group_ids=tuple(payload.get("groups", ["everyone"])),
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expirée. Reconnectez-vous.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token d'authentification invalide.",
            )

    # ── Dev header fallback (disabled in production) ──────────────────────────
    if settings.dev_auth_enabled and settings.app_env != "prod":
        tenant_id = x_tenant_id or settings.default_tenant_id
        user_id = x_user_id or "dev-user"
        group_ids = tuple(
            g.strip()
            for g in (x_user_groups or "everyone").split(",")
            if g.strip()
        )
        return Principal(
            tenant_id=tenant_id,
            user_id=user_id,
            email=x_user_email,
            display_name=None,
            group_ids=group_ids,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise.",
        headers={"WWW-Authenticate": "Bearer"},
    )
