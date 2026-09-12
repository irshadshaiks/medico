"""Patient-side routes: create a visit, give consent, run the intake."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import current_patient, current_user, patient_visit
from app.core.errors import Conflict, Forbidden, NotFound
from app.db.session import get_db
from app.models.clinical import Conversation, RedFlag, Visit
from app.models.enums import ConsentScope, ConversationStatus, VisitStatus
from app.models.user import Consent, PatientProfile, User
from app.schemas.clinical import VisitOut
from app.schemas.conversation import (
    AnswerRequest,
    ConsentRequest,
    ConversationOut,
    NextQuestionOut,
    QuestionOut,
    RedFlagOut,
    StartIntakeRequest,
)
from app.services import audit_service, conversation_service
from app.services.questioning.pathway_engine import progress
from app.services.questioning.schema import get_pathway

router = APIRouter(prefix="/patient", tags=["patient"])


@router.post("/visits", response_model=VisitOut, status_code=201)
async def create_visit(
    request: Request,
    department: str | None = None,
    patient: PatientProfile = Depends(current_patient),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> VisitOut:
    open_visit = await db.execute(
        select(Visit).where(
            Visit.patient_id == patient.id,
            Visit.status.in_([VisitStatus.INTAKE_STARTED, VisitStatus.INTAKE_COMPLETE, VisitStatus.IN_REVIEW]),
        )
    )
    existing = open_visit.scalar_one_or_none()
    if existing is not None:
        # Resuming beats stranding a half-finished intake behind a new one.
        return VisitOut.model_validate(existing)

    visit = Visit(patient_id=patient.id, department=department, language=user.preferred_language)
    db.add(visit)
    await db.flush()
    await audit_service.record(
        db, event=audit_service.AuditEvent.VISIT_CREATED, actor_id=user.id, actor_role="patient",
        entity_type="visit", entity_id=visit.id,
    )
    await db.commit()
    return VisitOut.model_validate(visit)


@router.get("/visits/current", response_model=VisitOut | None)
async def current_visit(
    patient: PatientProfile = Depends(current_patient), db: AsyncSession = Depends(get_db)
) -> VisitOut | None:
    result = await db.execute(
        select(Visit)
        .where(Visit.patient_id == patient.id)
        .order_by(Visit.created_at.desc())
        .limit(1)
    )
    visit = result.scalar_one_or_none()
    return VisitOut.model_validate(visit) if visit else None


@router.post("/visits/{visit_id}/consent", status_code=201)
async def give_consent(
    payload: ConsentRequest,
    visit: Visit = Depends(patient_visit),
    patient: PatientProfile = Depends(current_patient),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        scope = ConsentScope(payload.scope)
    except ValueError as exc:
        raise Conflict(f"'{payload.scope}' is not a consent scope.") from exc

    existing = (
        await db.execute(
            select(Consent).where(
                Consent.patient_id == patient.id, Consent.visit_id == visit.id, Consent.scope == scope
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if existing is None:
        existing = Consent(patient_id=patient.id, visit_id=visit.id, scope=scope, granted=payload.granted)
        db.add(existing)

    existing.granted = payload.granted
    existing.language_shown = payload.language_shown
    existing.consent_text_version = payload.consent_text_version
    existing.consent_text = payload.consent_text
    if payload.granted:
        existing.granted_at, existing.withdrawn_at = now, None
    else:
        existing.withdrawn_at = now
    await db.flush()

    await audit_service.record(
        db,
        event=audit_service.AuditEvent.CONSENT_GRANTED if payload.granted else audit_service.AuditEvent.CONSENT_WITHDRAWN,
        actor_id=user.id, actor_role="patient", entity_type="consent", entity_id=existing.id,
        summary=f"{scope.value} consent {'granted' if payload.granted else 'withdrawn'}.",
    )
    await db.commit()
    return {"scope": scope.value, "granted": payload.granted}


@router.post("/visits/{visit_id}/intake", response_model=NextQuestionOut, status_code=201)
async def start_intake(
    payload: StartIntakeRequest,
    visit: Visit = Depends(patient_visit),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> NextQuestionOut:
    conversation, question, presented = await conversation_service.start(
        db, visit=visit, chief_complaint=payload.chief_complaint, language=payload.language, actor_id=user.id
    )
    await db.commit()

    pathway = get_pathway(conversation.detected_pathway or "generic")
    _, total = progress(pathway, [])
    return NextQuestionOut(
        conversation_id=conversation.id,
        status=conversation.status,
        question=QuestionOut.model_validate(question) if question else None,
        step_index=0,
        total_steps=total,
        complete=question is None,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    patient: PatientProfile = Depends(current_patient),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    conversation = await conversation_service.get_conversation(db, conversation_id)
    visit = await db.get(Visit, conversation.visit_id)
    if visit is None or visit.patient_id != patient.id:
        raise NotFound("That intake session could not be found.")
    return ConversationOut.model_validate(conversation)


@router.get("/conversations/{conversation_id}/next-question", response_model=NextQuestionOut)
async def next_question(
    conversation_id: uuid.UUID,
    patient: PatientProfile = Depends(current_patient),
    db: AsyncSession = Depends(get_db),
) -> NextQuestionOut:
    """Also the resume endpoint — a refreshed kiosk calls this and continues."""
    conversation = await conversation_service.get_conversation(db, conversation_id)
    visit = await db.get(Visit, conversation.visit_id)
    if visit is None or visit.patient_id != patient.id:
        raise NotFound("That intake session could not be found.")

    question, _ = await conversation_service.ask_next(db, conversation)
    await db.commit()

    return NextQuestionOut(
        conversation_id=conversation.id,
        status=conversation.status,
        question=QuestionOut.model_validate(question) if question else None,
        step_index=conversation.current_step_index,
        total_steps=max(conversation.current_step_index + 1, 1),
        complete=question is None,
    )


@router.post("/conversations/{conversation_id}/answer", response_model=NextQuestionOut)
async def submit_answer(
    conversation_id: uuid.UUID,
    payload: AnswerRequest,
    patient: PatientProfile = Depends(current_patient),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> NextQuestionOut:
    conversation = await conversation_service.get_conversation(db, conversation_id)
    visit = await db.get(Visit, conversation.visit_id)
    if visit is None or visit.patient_id != patient.id:
        raise NotFound("That intake session could not be found.")

    flags, question, _ = await conversation_service.submit_answer(
        db,
        conversation=conversation,
        question_id=payload.question_id,
        text=payload.text,
        via_voice=payload.via_voice,
        client_token=payload.client_token,
        actor_id=user.id,
    )
    await db.commit()

    return NextQuestionOut(
        conversation_id=conversation.id,
        status=conversation.status,
        question=QuestionOut.model_validate(question) if question else None,
        step_index=conversation.current_step_index,
        total_steps=max(conversation.current_step_index + 1, 1),
        new_red_flags=[RedFlagOut.model_validate(f) for f in flags],
        complete=question is None,
    )


@router.get("/conversations/{conversation_id}/red-flags", response_model=list[RedFlagOut])
async def red_flags(
    conversation_id: uuid.UUID,
    patient: PatientProfile = Depends(current_patient),
    db: AsyncSession = Depends(get_db),
) -> list[RedFlagOut]:
    conversation = await conversation_service.get_conversation(db, conversation_id)
    visit = await db.get(Visit, conversation.visit_id)
    if visit is None or visit.patient_id != patient.id:
        raise NotFound("That intake session could not be found.")
    result = await db.execute(select(RedFlag).where(RedFlag.visit_id == visit.id))
    return [RedFlagOut.model_validate(f) for f in result.scalars()]
