"""Identity: users, the two role profiles, refresh tokens and consent records."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ConsentScope, Language, Role


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # bcrypt output is 60 chars; 128 leaves room for an algorithm change.
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role_enum"), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[Language] = mapped_column(
        Enum(Language, name="language_enum"), default=Language.EN, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient_profile: Mapped["PatientProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class PatientProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "patient_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(16))
    blood_group: Mapped[str | None] = mapped_column(String(8))
    address_district: Mapped[str | None] = mapped_column(String(120))
    emergency_contact: Mapped[str | None] = mapped_column(String(120))

    # Simulated only. Format is deliberately unlike a real ABHA number — see
    # app/services/abdm/mock_adapter.py.
    abha_id: Mapped[str | None] = mapped_column(String(32), index=True)
    abha_linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Consent withdrawal soft-deletes rather than destroying the audit trail.
    consent_withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="patient_profile")
    visits: Mapped[list["Visit"]] = relationship(back_populates="patient")  # noqa: F821

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class DoctorProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    registration_number: Mapped[str | None] = mapped_column(String(64))
    department: Mapped[str | None] = mapped_column(String(120), index=True)
    designation: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="doctor_profile")


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    """
    Stored so a refresh token can be revoked. Access tokens stay stateless and
    short-lived; only the long-lived credential needs a server-side record.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class Consent(Base, UUIDMixin, TimestampMixin):
    """
    Explicit, scoped, revocable. The intake flow refuses to start without an
    active `intake` consent for the visit.
    """

    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("patient_id", "visit_id", "scope", name="uq_consent_scope"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[ConsentScope] = mapped_column(Enum(ConsentScope, name="consent_scope_enum"), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language_shown: Mapped[Language] = mapped_column(
        Enum(Language, name="language_enum", create_type=False), default=Language.EN, nullable=False
    )
    # The exact wording the patient agreed to, kept verbatim for the audit trail.
    consent_text_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    consent_text: Mapped[str | None] = mapped_column(Text)
