"""
Document upload and retrieval. Files are never served without an auth check.

The processing flow is deliberately self-healing. The original version handed
OCR to a FastAPI background task and let the client poll `ocr_status`; when
that task died -- a missing Tesseract binary, a worker recycled mid-job, an
exception raised before the status column was written -- the row stayed at
`queued` forever and the UI polled a job that no longer existed. That is the
failure mode where the document section simply stops responding, with nothing
in the interface to explain why.

Three changes fix it:

  * A **stall watchdog**. If a poll finds a job still queued or processing past
    a deadline, the request reclaims and runs it inline rather than waiting for
    a worker that is not coming back.
  * An explicit **retry** endpoint, so a failure is recoverable without making
    the patient photograph the document again.
  * **Failures are terminal and visible.** `ocr_status` reaches `failed` with a
    readable reason, so the client stops polling instead of spinning forever.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, patient_visit
from app.core.config import settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.clinical import Visit
from app.models.document import DocumentExtraction, MedicalDocument
from app.models.enums import OCRStatus, Role
from app.models.user import User
from app.schemas.clinical import DocumentDetailOut, DocumentOut, ExtractionOut
from app.services import audit_service, document_service
from app.services.storage.factory import get_storage_service

log = get_logger(__name__)
router = APIRouter(tags=["documents"])

# How long a job may sit before a poll reclaims it. Generous enough that a
# genuinely slow multi-page PDF is not interrupted, short enough that a dead
# worker is noticed within one poll cycle.
STALL_SECONDS = 90


@router.post("/patient/visits/{visit_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    # Form, not a query parameter. A multipart POST that also carries query
    # args is a common source of silent 422s from the browser side.
    from_camera: bool = Form(default=False),
    process_inline: bool = Query(
        default=False,
        description="Run OCR before responding. Slower, but removes the polling step entirely.",
    ),
    visit: Visit = Depends(patient_visit),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    data = await file.read()
    mime = document_service.validate_upload(
        data, file.content_type or "", settings.MAX_UPLOAD_BYTES, settings.ALLOWED_UPLOAD_MIME
    )

    document = await document_service.store_upload(
        db,
        visit=visit,
        filename=file.filename or "upload",
        data=data,
        mime_type=mime,
        from_camera=from_camera,
        actor_id=user.id,
    )
    # Committed before processing starts, so the upload survives even if OCR
    # then fails. Losing the original because extraction broke would be far
    # worse than showing an extraction error next to a stored document.
    await db.commit()
    document_id = document.id

    if process_inline:
        await document_service.process_document(document_id)
        await db.refresh(document)
    else:
        background.add_task(document_service.process_document, document_id)

    return DocumentOut.model_validate(document)


async def _readable_document(document_id: uuid.UUID, user: User, db: AsyncSession) -> MedicalDocument:
    """Owning patient, or any doctor. Everyone else gets the same 404."""
    document = await db.get(MedicalDocument, document_id)
    if document is None:
        raise NotFound("That document could not be found.")

    if user.role is Role.PATIENT:
        if user.patient_profile is None or document.patient_id != user.patient_profile.id:
            # Identical to genuinely-missing, so the API does not confirm which
            # document ids exist to someone probing them.
            raise NotFound("That document could not be found.")
    elif user.role not in (Role.DOCTOR, Role.ADMIN):
        raise Forbidden("Your account does not have access to this.")
    return document


def _is_stalled(extraction: DocumentExtraction) -> bool:
    if extraction.ocr_status not in (OCRStatus.QUEUED, OCRStatus.PROCESSING):
        return False
    reference = extraction.updated_at or extraction.created_at
    if reference is None:
        return True
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return datetime.now(UTC) - reference > timedelta(seconds=STALL_SECONDS)


@router.get("/documents/{document_id}/extraction", response_model=ExtractionOut)
async def get_extraction(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractionOut:
    """
    Polled by the client while processing runs.

    If the job has stalled this reclaims it inline, so the patient standing at
    the kiosk gets a result instead of a spinner that never resolves.
    """
    document = await _readable_document(document_id, user, db)
    extraction = (
        await db.execute(select(DocumentExtraction).where(DocumentExtraction.document_id == document.id))
    ).scalar_one_or_none()

    if extraction is None:
        # The row should always exist. If it does not, the upload half-failed --
        # recreate and process rather than 404 on a document that is right there.
        extraction = DocumentExtraction(document_id=document.id, ocr_status=OCRStatus.QUEUED)
        db.add(extraction)
        await db.commit()
        await document_service.process_document(document.id)
        await db.refresh(extraction)
        return ExtractionOut.model_validate(extraction)

    if _is_stalled(extraction):
        log.warning(
            "Reclaiming a stalled OCR job",
            extra={"extra": {"document_id": str(document.id), "status": extraction.ocr_status.value}},
        )
        await document_service.process_document(document.id)
        await db.refresh(extraction)

    return ExtractionOut.model_validate(extraction)


@router.post("/documents/{document_id}/retry", response_model=ExtractionOut)
async def retry_extraction(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractionOut:
    """
    Re-run OCR and extraction on a document that failed.

    Runs inline: this is an explicit user action, and handing it back to a
    background task would reproduce exactly the failure being retried.
    """
    document = await _readable_document(document_id, user, db)
    extraction = (
        await db.execute(select(DocumentExtraction).where(DocumentExtraction.document_id == document.id))
    ).scalar_one_or_none()

    if extraction and extraction.ocr_status is OCRStatus.PROCESSING and not _is_stalled(extraction):
        raise Conflict("This document is being read right now. Wait a moment before retrying.")

    if extraction is None:
        extraction = DocumentExtraction(document_id=document.id)
        db.add(extraction)
    extraction.ocr_status = OCRStatus.QUEUED
    extraction.ocr_error = None
    await db.commit()

    await document_service.process_document(document.id)
    await db.refresh(extraction)

    await audit_service.record(
        db,
        event="document.extraction_retried",
        actor_id=user.id,
        actor_role=user.role.value,
        entity_type="document",
        entity_id=document.id,
    )
    await db.commit()
    return ExtractionOut.model_validate(extraction)


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailOut:
    document = await _readable_document(document_id, user, db)
    extraction = (
        await db.execute(select(DocumentExtraction).where(DocumentExtraction.document_id == document.id))
    ).scalar_one_or_none()

    storage = get_storage_service()
    url = await storage.presigned_url(document.storage_key)

    await audit_service.record(
        db,
        event=audit_service.AuditEvent.DOCUMENT_VIEWED,
        actor_id=user.id,
        actor_role=user.role.value,
        entity_type="document",
        entity_id=document.id,
    )
    await db.commit()

    return DocumentDetailOut(
        document=DocumentOut.model_validate(document),
        extraction=ExtractionOut.model_validate(extraction) if extraction else None,
        download_url=url,
    )


@router.get("/documents/{document_id}/file")
async def download_document(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Authenticated proxy for local storage, and the fallback path for S3.

    `attachment` plus `nosniff` means an uploaded file is never rendered or
    executed inside the application's own origin -- a photographed document
    that happens to contain markup stays inert.
    """
    document = await _readable_document(document_id, user, db)
    storage = get_storage_service()
    data = await storage.get(document.storage_key)
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/patient/visits/{visit_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    visit: Visit = Depends(patient_visit), db: AsyncSession = Depends(get_db)
) -> list[DocumentOut]:
    result = await db.execute(
        select(MedicalDocument).where(MedicalDocument.visit_id == visit.id).order_by(MedicalDocument.created_at)
    )
    return [DocumentOut.model_validate(d) for d in result.scalars()]
