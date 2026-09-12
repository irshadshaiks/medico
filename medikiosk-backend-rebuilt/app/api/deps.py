"""
Request dependencies: who is calling, and what they are allowed to touch.

The role guards are the cheap half. The important half is
`patient_visit` / `doctor_visit`, which check that *this* patient owns *this*
visit — role alone would happily let one patient read another's record by
changing a UUID in the URL.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.security import decode_token
from app.db.session import get_db
from app.models.clinical import Visit
from app.models.enums import Role
from app.models.user import DoctorProfile, PatientProfile, User

bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise Unauthorized("Sign in to continue.")

    payload = decode_token(credentials.credentials, expect="access")
    if payload is None:
        raise Unauthorized("Your session has expired. Sign in again.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("That sign-in token is not valid.") from exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.patient_profile), selectinload(User.doctor_profile))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise Unauthorized("That account is no longer active.")
    return user


def require_role(*roles: Role) -> Callable:
    async def guard(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise Forbidden("Your account does not have access to this.")
        return user

    return guard


require_patient = require_role(Role.PATIENT)
require_doctor = require_role(Role.DOCTOR, Role.ADMIN)
require_admin = require_role(Role.ADMIN)


async def current_patient(user: User = Depends(require_patient)) -> PatientProfile:
    if user.patient_profile is None:
        raise NotFound("This account has no patient profile yet.")
    return user.patient_profile


async def current_doctor(user: User = Depends(require_doctor)) -> DoctorProfile:
    if user.doctor_profile is None:
        raise NotFound("This account has no doctor profile yet.")
    return user.doctor_profile


async def patient_visit(
    visit_id: uuid.UUID,
    patient: PatientProfile = Depends(current_patient),
    db: AsyncSession = Depends(get_db),
) -> Visit:
    """A patient may only ever reach their own visit."""
    visit = await db.get(Visit, visit_id)
    if visit is None or visit.patient_id != patient.id:
        # Same message either way: 'not found' and 'not yours' must be
        # indistinguishable, or the API confirms which visit IDs exist.
        raise NotFound("That visit could not be found.")
    return visit


async def doctor_visit(
    visit_id: uuid.UUID,
    doctor: DoctorProfile = Depends(current_doctor),
    db: AsyncSession = Depends(get_db),
) -> Visit:
    """
    Doctors reach any visit in the queue — an OPD reassigns constantly and a
    hard assignment lock would break the workflow. Every access is audited, and
    finalising is still attributed to the individual who did it.
    """
    visit = await db.get(Visit, visit_id)
    if visit is None:
        raise NotFound("That visit could not be found.")
    return visit


def client_ip(request: Request) -> str | None:
    # Behind ALB or CloudFront the socket address is the proxy's.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
