"""Registration, login, refresh and logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, current_user
from app.core.config import settings
from app.core.errors import Conflict, Unauthorized
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import DoctorProfile, PatientProfile, RefreshToken, User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue(db: AsyncSession, user: User, user_agent: str | None) -> TokenPair:
    access = create_access_token(str(user.id), user.role.value)
    refresh, jti, expires_at = create_refresh_token(str(user.id), user.role.value)
    db.add(
        RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at, user_agent=(user_agent or "")[:255] or None)
    )
    await db.flush()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenPair, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> TokenPair:
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise Conflict("An account already exists for that email address.")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=payload.role,
        phone=payload.phone,
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    await db.flush()

    if payload.role is Role.PATIENT:
        db.add(PatientProfile(user_id=user.id, date_of_birth=payload.date_of_birth, sex=payload.sex))
    else:
        db.add(DoctorProfile(user_id=user.id))
    await db.flush()

    tokens = await _issue(db, user, request.headers.get("user-agent"))
    await audit_service.record(
        db, event=audit_service.AuditEvent.REGISTER, actor_id=user.id, actor_role=user.role.value,
        entity_type="user", entity_id=user.id, ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return tokens


@router.post("/login", response_model=TokenPair)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    # One message for a wrong password and for an address with no account:
    # otherwise this endpoint tells an attacker which emails are registered.
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        if user is not None:
            await audit_service.record(
                db, event=audit_service.AuditEvent.LOGIN_FAILED, actor_id=user.id,
                entity_type="user", entity_id=user.id, ip_address=client_ip(request),
            )
            await db.commit()
        raise Unauthorized("That email address and password do not match.")

    user.last_login_at = datetime.now(UTC)
    tokens = await _issue(db, user, request.headers.get("user-agent"))
    await audit_service.record(
        db, event=audit_service.AuditEvent.LOGIN, actor_id=user.id, actor_role=user.role.value,
        entity_type="user", entity_id=user.id, ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
async def refresh(request: Request, payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    claims = decode_token(payload.refresh_token, expect="refresh")
    if claims is None:
        raise Unauthorized("Your session has expired. Sign in again.")

    stored = (
        await db.execute(select(RefreshToken).where(RefreshToken.jti == claims.get("jti")))
    ).scalar_one_or_none()
    if stored is None or stored.revoked_at is not None or stored.expires_at < datetime.now(UTC):
        raise Unauthorized("Your session has expired. Sign in again.")

    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("That account is no longer active.")

    # Rotation: the presented token is spent, so a stolen copy is single-use.
    stored.revoked_at = datetime.now(UTC)
    tokens = await _issue(db, user, request.headers.get("user-agent"))
    await db.commit()
    return tokens


@router.post("/logout", status_code=204)
async def logout(
    request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await db.execute(
        RefreshToken.__table__.update()
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await audit_service.record(
        db, event=audit_service.AuditEvent.LOGOUT, actor_id=user.id, actor_role=user.role.value,
        entity_type="user", entity_id=user.id, ip_address=client_ip(request),
    )
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)
