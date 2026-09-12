"""
The timeline.

Pure aggregation across five tables into one dated sequence. The hard part is
dates: OCR yields partial and sometimes absent ones, so entries carry
`date_uncertain` and undated entries sort to the end rather than being dropped
or silently given today's date.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical import Visit
from app.models.document import Investigation, MedicalDocument, MedicalHistoryEntry, Medication
from app.models.enums import Provenance


@dataclass(slots=True)
class TimelineEvent:
    id: str
    kind: str  # visit | investigation | medication | history | document
    title: str
    detail: str
    provenance: Provenance
    occurred_on: date | None
    date_uncertain: bool = False
    current_visit: bool = False
    source_document_ids: list[str] = field(default_factory=list)


async def build(db: AsyncSession, patient_id: uuid.UUID, current_visit_id: uuid.UUID | None = None) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []

    visits = (await db.execute(select(Visit).where(Visit.patient_id == patient_id))).scalars()
    for visit in visits:
        events.append(
            TimelineEvent(
                id=str(visit.id),
                kind="visit",
                title=visit.chief_complaint or "Outpatient visit",
                detail=f"Recorded during intake. Queue: {visit.priority_level.value}.",
                provenance=Provenance.PATIENT_PROVIDED,
                occurred_on=(visit.queued_at or visit.created_at).date(),
                current_visit=(visit.id == current_visit_id),
            )
        )

    investigations = (
        await db.execute(select(Investigation).where(Investigation.patient_id == patient_id))
    ).scalars()
    for inv in investigations:
        value = " ".join(part for part in [inv.value, inv.unit] if part)
        detail = f"{value}" + (f" (reference {inv.reference_range})" if inv.reference_range else "")
        if inv.abnormal_flag and inv.abnormal_flag != "normal":
            detail += f" — marked {inv.abnormal_flag} on the report."
        events.append(
            TimelineEvent(
                id=str(inv.id), kind="investigation", title=inv.name, detail=detail.strip(),
                provenance=inv.provenance, occurred_on=inv.performed_on,
                date_uncertain=inv.date_uncertain,
                source_document_ids=[str(s) for s in (inv.source_document_ids or [])],
            )
        )

    medications = (await db.execute(select(Medication).where(Medication.patient_id == patient_id))).scalars()
    for med in medications:
        detail = " · ".join(part for part in [med.dose, med.frequency, med.duration] if part)
        if med.source_count > 1:
            detail += f" — confirmed by {med.source_count} documents."
        events.append(
            TimelineEvent(
                id=str(med.id), kind="medication", title=med.name, detail=detail.strip(" ·"),
                provenance=med.provenance, occurred_on=med.started_on,
                source_document_ids=[str(s) for s in (med.source_document_ids or [])],
            )
        )

    history = (
        await db.execute(select(MedicalHistoryEntry).where(MedicalHistoryEntry.patient_id == patient_id))
    ).scalars()
    for entry in history:
        events.append(
            TimelineEvent(
                id=str(entry.id), kind="history", title=entry.label, detail=entry.detail or "",
                provenance=entry.provenance, occurred_on=entry.onset_date,
                date_uncertain=entry.date_uncertain,
            )
        )

    documents = (
        await db.execute(select(MedicalDocument).where(MedicalDocument.patient_id == patient_id))
    ).scalars()
    for doc in documents:
        events.append(
            TimelineEvent(
                id=str(doc.id), kind="document",
                title=doc.original_filename,
                detail=f"{(doc.document_type.value if doc.document_type else 'document').replace('_', ' ').title()} uploaded during intake.",
                provenance=Provenance.DOCUMENT_EXTRACTED,
                occurred_on=doc.created_at.date(),
                current_visit=(doc.visit_id == current_visit_id),
                source_document_ids=[str(doc.id)],
            )
        )

    # Oldest first; anything undated goes last rather than being invented a date.
    events.sort(key=lambda e: (e.occurred_on is None, e.occurred_on or date.min))
    return events
