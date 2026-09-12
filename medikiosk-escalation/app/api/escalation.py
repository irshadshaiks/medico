"""
Safety screen and escalation endpoints.

`/safety-screen` runs before `/intake`. That ordering is the point: the danger
question is asked before we know the complaint, before a pathway is selected,
and before any clinical question is phrased.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_patient, current_user, patient_visit, require_doctor
from app.core.errors import NotFound
from app.db.session import get_db
from app.models.clinical import Visit
from app.models.user import PatientProfile, User
from app.schemas.escalation import (
    AcknowledgeRequest,
    EscalationOut,
    SafetyScreenAnswer,
    SafetyScreenOut,
    StaffEscalationOut,
)
from app.schemas.conversation import QuestionOut
from app.services.escalation import screen_service
from app.services.escalation import service as escalation_service

router = APIRouter(tags=["safety"])


@router.post("/patient/visits/{visit_id}/safety-screen", response_model=SafetyScreenOut)
async def get_safety_screen(
    visit: Visit = Depends(patient_visit),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SafetyScreenOut:
    conversation, question = await screen_service.present(
        db, visit=visit, language=user.preferred_language
    )
    await db.commit()
    return SafetyScreenOut(
        conversation_id=conversation.id, question=QuestionOut.model_validate(question)
    )


@router.post("/patient/visits/{visit_id}/safety-screen/answer", response_model=EscalationOut)
async def answer_safety_screen(
    payload: SafetyScreenAnswer,
    visit: Visit = Depends(patient_visit),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> EscalationOut:
    escalation = await screen_service.submit(
        db,
        visit=visit,
        conversation_id=payload.conversation_id,
        question_id=payload.question_id,
        text=payload.text,
        respondent=payload.respondent,
        attendant_relationship=payload.attendant_relationship,
        actor_id=user.id,
    )
    await db.commit()

    if escalation is None:
        return EscalationOut(escalated=False)
    return EscalationOut(
        escalated=True,
        id=escalation.id,
        instruction=escalation.patient_instruction,
        destination=escalation.destination,
        clinically_signed_off=escalation.clinically_signed_off,
    )


@router.get("/staff/escalations", response_model=list[StaffEscalationOut], dependencies=[Depends(require_doctor)])
async def open_escalations(db: AsyncSession = Depends(get_db)) -> list[StaffEscalationOut]:
    """
    The triage desk screen. Polled every few seconds.

    Unacknowledged alerts never expire on their own — an alarm that clears
    itself looks calm while nobody has gone to fetch anyone.
    """
    now = datetime.now(UTC)
    out: list[StaffEscalationOut] = []

    for escalation in await escalation_service.open_escalations(db):
        visit = await db.get(Visit, escalation.visit_id)
        profile = await db.get(PatientProfile, visit.patient_id) if visit else None
        patient_user = await db.get(User, profile.user_id) if profile else None
        raised = escalation.created_at
        if raised.tzinfo is None:
            raised = raised.replace(tzinfo=UTC)

        out.append(
            StaffEscalationOut(
                id=escalation.id,
                visit_id=escalation.visit_id,
                patient_name=patient_user.full_name if patient_user else "Unknown",
                patient_age=profile.age if profile else None,
                rule_id=escalation.rule_id,
                staff_label=escalation.staff_label,
                destination=escalation.destination,
                evidence=escalation.evidence,
                clinically_signed_off=escalation.clinically_signed_off,
                raised_at=escalation.created_at,
                waiting_seconds=int((now - raised).total_seconds()),
            )
        )
    return out


@router.post("/staff/escalations/{escalation_id}/acknowledge", dependencies=[Depends(require_doctor)])
async def acknowledge(
    escalation_id: uuid.UUID,
    payload: AcknowledgeRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    escalation = await escalation_service.acknowledge(
        db, escalation_id=escalation_id, staff_user_id=user.id,
        outcome=payload.outcome, note=payload.note,
    )
    if escalation is None:
        raise NotFound("That alert could not be found.")
    await db.commit()
    return {"acknowledged": True, "outcome": payload.outcome}
