"""Password hashing and JWT issue/verify. Nothing else touches these primitives."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITHM = "HS256"

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _pwd.verify(raw, hashed)
    except ValueError:
        # Malformed hash in the row — treat as a failed login, never a 500.
        return False


def _encode(subject: str, role: str, kind: Literal["access", "refresh"], ttl: timedelta) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": kind,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM), jti


def create_access_token(user_id: str, role: str) -> str:
    token, _ = _encode(user_id, role, "access", timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES))
    return token


def create_refresh_token(user_id: str, role: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expiry). The jti is stored so it can be revoked."""
    ttl = timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    token, jti = _encode(user_id, role, "refresh", ttl)
    return token, jti, datetime.now(UTC) + ttl


def decode_token(token: str, expect: Literal["access", "refresh"]) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expect:
        return None
    return payload
