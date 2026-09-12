"""
The document pipeline.

upload → validate → store original → OCR → classify → extract → normalize.

Runs as a FastAPI background task rather than Celery: the work is a handful of
seconds, the queue would be one more moving part to keep alive on demo day, and
job state already lives in `DocumentExtraction.ocr_status` where the client
polls it. That choice is worth revisiting if throughput ever matters.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.core.logging import get_logger
from app.core.prompts import DOCUMENT_CLASSIFICATION, build_extraction_prompt
from app.db.session import SessionLocal
from app.models.clinical import Visit
from app.models.document import (
    Allergy,
    DocumentExtraction,
    Investigation,
    MedicalDocument,
    Medication,
)
from app.models.enums import DocumentType, OCRStatus, Provenance
from app.services import audit_service
from app.services.ai.base import AICompletionRequest
from app.services.ai.factory import get_ai_service
from app.services.ocr.factory import get_ocr_service
from app.services.storage.factory import get_storage_service

log = get_logger(__name__)

# Real file signatures. An extension check alone is trivially bypassed by
# renaming, and this endpoint accepts uploads from the public internet.
MAGIC = {
    b"%PDF": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}


def sniff_mime(data: bytes) -> str | None:
    for signature, mime in MAGIC.items():
        if data.startswith(signature):
            return mime
    return None


def validate_upload(data: bytes, declared_mime: str, max_bytes: int, allowed: list[str]) -> str:
    if not data:
        raise ValidationFailed("That file appears to be empty. Try taking the photo again.")
    if len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValidationFailed(f"That file is larger than {mb} MB. Try a photo of a single page.")

    actual = sniff_mime(data)
    if actual is None:
        raise ValidationFailed("Only PDF, JPG and PNG files can be read. That file is something else.")
    if actual not in allowed:
        raise ValidationFailed(f"{actual} files cannot be read here. Upload a PDF, JPG or PNG.")
    if declared_mime and declared_mime != actual:
        # Not fatal — browsers get this wrong routinely — but worth recording.
        log.info("Declared MIME did not match content", extra={"extra": {"declared": declared_mime, "actual": actual}})
    return actual


async def store_upload(
    db: AsyncSession,
    *,
    visit: Visit,
    filename: str,
    data: bytes,
    mime_type: str,
    from_camera: bool,
    actor_id: uuid.UUID,
) -> MedicalDocument:
    storage = get_storage_service()
    # Opaque key: nothing about it can be guessed from the patient's identity.
    key = f"visits/{visit.id}/{uuid.uuid4().hex}"
    stored = await storage.put(key, data, mime_type)

    document = MedicalDocument(
        visit_id=visit.id,
        patient_id=visit.patient_id,
        original_filename=filename[:255],
        storage_key=stored.key,
        mime_type=mime_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        captured_via_camera=from_camera,
    )
    db.add(document)
    await db.flush()

    db.add(DocumentExtraction(document_id=document.id, ocr_status=OCRStatus.QUEUED))
    await db.flush()

    await audit_service.record(
        db,
        event=audit_service.AuditEvent.DOCUMENT_UPLOADED,
        actor_id=actor_id,
        actor_role="patient",
        entity_type="document",
        entity_id=document.id,
        summary=f"Uploaded {filename[:80]} ({stored.size_bytes} bytes).",
    )
    return document


async def process_document(document_id: uuid.UUID) -> None:
    """
    Background worker. Opens its own session — the request that scheduled it is
    long gone by the time this runs, and its session with it.
    """
    async with SessionLocal() as db:
        try:
            await _process(db, document_id)
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - a failed document must not kill the worker
            await db.rollback()
            log.error(
                "Document processing failed",
                extra={"extra": {"document_id": str(document_id), "error": str(exc)[:300]}},
            )
            async with SessionLocal() as recovery:
                extraction = (
                    await recovery.execute(
                        select(DocumentExtraction).where(DocumentExtraction.document_id == document_id)
                    )
                ).scalar_one_or_none()
                if extraction:
                    extraction.ocr_status = OCRStatus.FAILED
                    extraction.ocr_error = str(exc)[:500]
                    await recovery.commit()


async def _process(db: AsyncSession, document_id: uuid.UUID) -> None:
    document = await db.get(MedicalDocument, document_id)
    if document is None:
        return
    extraction = (
        await db.execute(select(DocumentExtraction).where(DocumentExtraction.document_id == document_id))
    ).scalar_one_or_none()
    if extraction is None:
        extraction = DocumentExtraction(document_id=document_id)
        db.add(extraction)

    extraction.ocr_status = OCRStatus.PROCESSING
    await db.flush()

    # ---------------------------------------------------------------- OCR --
    storage = get_storage_service()
    ocr = get_ocr_service()
    data = await storage.get(document.storage_key)
    result = await ocr.extract_text(data, document.mime_type)

    extraction.raw_text = result.text
    extraction.ocr_confidence = result.confidence
    extraction.ocr_provider = result.provider
    document.page_count = result.page_count

    if result.error or not result.text.strip():
        extraction.ocr_status = OCRStatus.FAILED
        extraction.ocr_error = result.error or "No readable text was found in this document."
        await db.flush()
        return

    await audit_service.record(
        db,
        event=audit_service.AuditEvent.OCR_COMPLETED,
        entity_type="document",
        entity_id=document.id,
        summary=f"OCR read {len(result.text)} characters via {result.provider}.",
    )

    # ----------------------------------------------------------- classify --
    ai = get_ai_service()
    classification = await ai.complete(
        AICompletionRequest(prompt=DOCUMENT_CLASSIFICATION.format(text=result.text[:4000]), temperature=0.0, max_output_tokens=12),
        fallback="other",
    )
    document.document_type = _to_document_type(classification.text)

    # ------------------------------------------------------------ extract --
    fields, degraded = await ai.complete_json(
        AICompletionRequest(prompt=build_extraction_prompt(result.text), temperature=0.0, max_output_tokens=1600),
        fallback={},
    )

    extraction.structured_fields = fields
    extraction.overall_confidence = _coerce_float(fields.get("overall_confidence")) or result.confidence
    extraction.extraction_provider = ai.name
    extraction.extracted_at = datetime.now(UTC)
    extraction.ocr_status = OCRStatus.DONE
    await db.flush()

    if not degraded and fields:
        await normalize(db, document=document, fields=fields)

    await audit_service.record(
        db,
        event=audit_service.AuditEvent.EXTRACTION_COMPLETED,
        entity_type="document",
        entity_id=document.id,
        summary=f"Extracted {len(fields.get('medications', []))} medications, "
        f"{len(fields.get('investigations', []))} investigations.",
    )


# ------------------------------------------------------------ normalization --


def normalize_name(value: str) -> str:
    """Loose but predictable: lowercase, strip dose forms and punctuation."""
    cleaned = re.sub(r"\b(tab|tablet|cap|capsule|syp|syrup|inj|injection)\b\.?", "", value.lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


async def normalize(db: AsyncSession, *, document: MedicalDocument, fields: dict[str, Any]) -> None:
    """
    Fold extracted entities into the patient-level tables.

    The same drug named on two prescriptions becomes one row with two sources
    and a source_count of two — which is more useful to a doctor than two rows,
    because agreement across documents is itself information.
    """
    patient_id = document.patient_id
    doc_id = str(document.id)
    doc_date = _parse_date(fields.get("document_date"))

    for entry in fields.get("medications") or []:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        key = normalize_name(name)
        existing = (
            await db.execute(
                select(Medication).where(Medication.patient_id == patient_id, Medication.normalized_name == key)
            )
        ).scalar_one_or_none()

        if existing:
            sources = list(existing.source_document_ids or [])
            if doc_id not in sources:
                sources.append(doc_id)
                existing.source_document_ids = sources
                existing.source_count = len(sources)
            # Keep the more confident reading of dose and frequency.
            if (_coerce_float(entry.get("confidence")) or 0) > (existing.confidence or 0):
                existing.dose = entry.get("dose") or existing.dose
                existing.frequency = entry.get("frequency") or existing.frequency
                existing.confidence = _coerce_float(entry.get("confidence"))
        else:
            db.add(
                Medication(
                    patient_id=patient_id,
                    name=name,
                    normalized_name=key,
                    dose=entry.get("dose"),
                    frequency=entry.get("frequency"),
                    duration=entry.get("duration"),
                    started_on=doc_date,
                    provenance=Provenance.DOCUMENT_EXTRACTED,
                    confidence=_coerce_float(entry.get("confidence")),
                    source_document_ids=[doc_id],
                    source_count=1,
                )
            )

    for entry in fields.get("investigations") or []:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        # A lab value is a point in time — the same test a year apart is two
        # results, not a duplicate. Deduplicated on name *and* date.
        key = normalize_name(name)
        existing = (
            await db.execute(
                select(Investigation).where(
                    Investigation.patient_id == patient_id,
                    Investigation.normalized_name == key,
                    Investigation.performed_on == doc_date,
                )
            )
        ).scalar_one_or_none()
        if existing:
            sources = list(existing.source_document_ids or [])
            if doc_id not in sources:
                existing.source_document_ids = sources + [doc_id]
            continue
        db.add(
            Investigation(
                patient_id=patient_id,
                name=name,
                normalized_name=key,
                value=str(entry.get("value")) if entry.get("value") is not None else None,
                unit=entry.get("unit"),
                reference_range=entry.get("reference_range"),
                abnormal_flag=entry.get("abnormal_flag"),
                performed_on=doc_date,
                date_uncertain=bool(fields.get("date_uncertain")),
                provenance=Provenance.DOCUMENT_EXTRACTED,
                confidence=_coerce_float(entry.get("confidence")),
                source_document_ids=[doc_id],
            )
        )

    for entry in fields.get("allergies") or []:
        substance = (entry.get("substance") or "").strip()
        if not substance:
            continue
        key = normalize_name(substance)
        existing = (
            await db.execute(
                select(Allergy).where(Allergy.patient_id == patient_id, Allergy.normalized_substance == key)
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            Allergy(
                patient_id=patient_id,
                substance=substance,
                normalized_substance=key,
                reaction=entry.get("reaction"),
                provenance=Provenance.DOCUMENT_EXTRACTED,
                confidence=_coerce_float(entry.get("confidence")),
                source_document_ids=[doc_id],
            )
        )

    await db.flush()


# ------------------------------------------------------------------ helpers --


def _to_document_type(value: str) -> DocumentType:
    cleaned = value.strip().lower().strip(".`\n ")
    try:
        return DocumentType(cleaned)
    except ValueError:
        return DocumentType.OTHER


def _coerce_float(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    """Accepts YYYY-MM-DD and YYYY-MM. OCR dates are often partial."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt, pad in (("%Y-%m-%d", None), ("%Y-%m", "-01")):
        try:
            return datetime.strptime(text + (pad or ""), "%Y-%m-%d").date()
        except ValueError:
            continue
    return None
