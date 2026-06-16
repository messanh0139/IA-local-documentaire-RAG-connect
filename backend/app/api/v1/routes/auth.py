from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    Principal,
    create_access_token,
    get_current_principal,
    hash_password,
    verify_password,
)
from app.db.session import get_db_session
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, PrincipalRead, RegisterRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user = await db.scalar(
        select(User).where(
            User.email == payload.email,
            User.tenant_id == settings.default_tenant_id,
        )
    )
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé. Contactez votre administrateur.",
        )
    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
    )
    return TokenResponse(
        access_token=token,
        email=user.email,
        display_name=user.display_name or user.email,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    allowed_domains = [d.strip().lstrip("@").lower() for d in settings.allowed_email_domains.split(",") if d.strip()]
    if allowed_domains:
        domain = payload.email.split("@")[-1].lower()
        if domain not in allowed_domains:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Inscription non autorisée. Seuls les emails @{', @'.join(allowed_domains)} sont acceptés.",
            )

    existing = await db.scalar(
        select(User).where(
            User.email == payload.email,
            User.tenant_id == settings.default_tenant_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà.",
        )

    tenant = await db.get(Tenant, settings.default_tenant_id)
    if not tenant:
        tenant = Tenant(id=settings.default_tenant_id, name=settings.default_tenant_id)
        db.add(tenant)

    display_name = payload.display_name or payload.email.split("@")[0]
    user = User(
        id=f"user-{uuid4()}",
        tenant_id=settings.default_tenant_id,
        external_id=payload.email,
        email=payload.email,
        display_name=display_name,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
    )
    return TokenResponse(
        access_token=token,
        email=user.email,
        display_name=user.display_name,
    )


@router.get("/me", response_model=PrincipalRead)
async def read_me(principal: Principal = Depends(get_current_principal)) -> PrincipalRead:
    return PrincipalRead(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        group_ids=list(principal.group_ids),
    )
