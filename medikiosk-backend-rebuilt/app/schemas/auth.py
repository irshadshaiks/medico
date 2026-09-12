from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Language, Role
from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.PATIENT
    phone: str | None = Field(default=None, max_length=20)
    preferred_language: Language = Language.EN
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=16)

    @field_validator("password")
    @classmethod
    def _not_trivial(cls, v: str) -> str:
        # Deliberately mild. A kiosk used by first-time internet users is worse
        # off with a rule that forces a password nobody can remember.
        if v.strip().lower() in {"password", "12345678", "medikiosk"}:
            raise ValueError("Choose a password that is harder to guess.")
        return v

    @field_validator("role")
    @classmethod
    def _no_self_serve_admin(cls, v: Role) -> Role:
        if v is Role.ADMIN:
            raise ValueError("Admin accounts cannot be self-registered.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    preferred_language: Language
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
