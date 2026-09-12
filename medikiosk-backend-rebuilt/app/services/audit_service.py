"""
The audit trail.

Called from the services that perform a sensitive action rather than from the
routes, so a new endpoint that reuses a service inherits the logging instead of
having to remember it.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, request_id_ctx
from app.models.record import AuditLog

log = get_logger(__name__)


class AuditEvent:
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    REGISTER = "auth.register"
    LOGOUT = "auth.logout"
    CONSENT_GRANTED = "consent.granted"
    CONSENT_WITHDRAWN = "consent.withdrawn"
    VISIT_CREATED = "visit.created"
    CONVERSATION_STARTED = "conversation.started"
    CONVERSATION_ANSWER = "conversation.answer"
    CONVERSATION_COMPLETED = "conversation.completed"
    RED_FLAG_RAISED = "redflag.raised"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_VIEWED = "document.viewed"
    OCR_COMPLETED = "document.ocr_completed"
    EXTRACTION_COMPLETED = "document.extraction_completed"
    SUMMARY_GENERATED = "summary.generated"
    SUMMARY_SECTION_VERIFIED = "summary.section_verified"
    SUMMARY_FINALIZED = "summary.finalized"
    EXTRACTION_VERIFIED = "extraction.verified"
    ABDM_LINKED = "abdm.linked"
    ABDM_EXPORTED = "abdm.exported"


async def record(
    db: AsyncSession,
    *,
    event: str,
    actor_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    summary: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            event=event,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            before=before,
            after=after,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:255] or None,
            request_id=request_id_ctx.get(),
        )
    )
    # Flushed with the caller's transaction: an action and its audit entry
    # commit together, or neither does.
    await db.flush()


async def trail(
    db: AsyncSession, entity_type: str, entity_id: uuid.UUID, limit: int = 200
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())
