"""
Demo seed.

Creates the four rehearsed scenarios so both portals look lived-in the moment
the app boots. Idempotent: re-running updates rather than duplicating, which
matters because a redeploy on demo morning should not double the queue.

Every name, number and document here is synthetic. No real patient data.

    python -m scripts.seed_demo_data
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.clinical import (
    Conversation,
    ConversationMessage,
    PatientResponse,
    Question,
    RedFlag,
    Visit,
)
from app.models.document import Investigation, MedicalHistoryEntry, Medication
from app.models.enums import (
    ConsentScope,
    ConversationStatus,
    HistoryType,
    Language,
    MessageRole,
    PriorityLevel,
    Provenance,
    Role,
    Severity,
    VerificationState,
    VisitStatus,
)
from app.models.record import ClinicalSummary, SummarySection
from app.models.user import Consent, DoctorProfile, PatientProfile, User
from app.services.questioning.pathway_engine import structure_answer
from app.services.questioning.schema import get_pathway

DEMO_PASSWORD = "MediKiosk#2026"


async def _user(db: AsyncSession, *, email: str, name: str, role: Role, language: Language) -> User:
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        return existing
    user = User(
        email=email, password_hash=hash_password(DEMO_PASSWORD), full_name=name,
        role=role, preferred_language=language,
    )
    db.add(user)
    await db.flush()
    return user


async def _patient(
    db: AsyncSession, *, email: str, name: str, dob: date, sex: str, language: Language
) -> PatientProfile:
    user = await _user(db, email=email, name=name, role=Role.PATIENT, language=language)
    profile = (
        await db.execute(select(PatientProfile).where(PatientProfile.user_id == user.id))
    ).scalar_one_or_none()
    if profile:
        return profile
    profile = PatientProfile(user_id=user.id, date_of_birth=dob, sex=sex, address_district="Bengaluru Urban")
    db.add(profile)
    await db.flush()
    return profile


async def _visit(
    db: AsyncSession,
    *,
    patient: PatientProfile,
    complaint: str,
    language: Language,
    status: VisitStatus,
    waited_minutes: int,
) -> Visit:
    existing = (
        await db.execute(select(Visit).where(Visit.patient_id == patient.id))
    ).scalar_one_or_none()
    if existing:
        return existing
    now = datetime.now(UTC)
    visit = Visit(
        patient_id=patient.id, chief_complaint=complaint, language=language, status=status,
        department="General Medicine", queued_at=now - timedelta(minutes=waited_minutes),
    )
    db.add(visit)
    await db.flush()
    db.add(
        Consent(
            patient_id=patient.id, visit_id=visit.id, scope=ConsentScope.INTAKE, granted=True,
            granted_at=now, language_shown=language,
            consent_text="Synthetic demo consent record.",
        )
    )
    await db.flush()
    return visit


async def _conversation(
    db: AsyncSession, *, visit: Visit, pathway_id: str, exchanges: list[tuple[str, str, str]]
) -> Conversation:
    """exchanges: (node_id, question asked, patient's answer)."""
    existing = (
        await db.execute(select(Conversation).where(Conversation.visit_id == visit.id))
    ).scalar_one_or_none()
    if existing:
        return existing

    conversation = Conversation(
        visit_id=visit.id, language=visit.language, detected_pathway=pathway_id,
        status=ConversationStatus.COMPLETED, completed_at=datetime.now(UTC),
        current_step_index=len(exchanges),
    )
    db.add(conversation)
    await db.flush()

    pathway = get_pathway(pathway_id)
    sequence = 1
    db.add(
        ConversationMessage(
            conversation_id=conversation.id, sequence=sequence, role=MessageRole.PATIENT,
            text=visit.chief_complaint or "", language=visit.language,
        )
    )

    for node_id, asked, answered in exchanges:
        node = next((n for n in pathway.nodes if n.id == node_id), None)
        question = Question(
            conversation_id=conversation.id, pathway=pathway_id, node_id=node_id,
            category=node.category if node else "general",
            canonical_text=node.question if node else asked, presented_text=asked,
            phrasing_source="template", answer_type=node.answer_type if node else "text",
            options=node.options if node else None,
        )
        db.add(question)
        await db.flush()

        sequence += 1
        db.add(
            ConversationMessage(
                conversation_id=conversation.id, sequence=sequence, role=MessageRole.SYSTEM,
                text=asked, language=visit.language,
            )
        )
        sequence += 1
        db.add(
            ConversationMessage(
                conversation_id=conversation.id, sequence=sequence, role=MessageRole.PATIENT,
                text=answered, language=visit.language, via_voice=True,
            )
        )
        db.add(
            PatientResponse(
                conversation_id=conversation.id, question_id=question.id,
                category=question.category, raw_text=answered,
                # Structured through the real engine, so seeded data exercises
                # exactly the same code path a live intake would.
                structured_value=structure_answer(node, answered) if node else {},
                provenance=Provenance.PATIENT_PROVIDED, via_voice=True,
            )
        )
        await db.flush()

    return conversation


async def seed(db: AsyncSession) -> dict:
    if not settings.ALLOW_DEMO_SEED:
        raise RuntimeError("Seeding is disabled. Set ALLOW_DEMO_SEED=true to run it.")

    doctor_user = await _user(
        db, email="doctor@medikiosk.demo", name="Dr. Meera Iyer", role=Role.DOCTOR, language=Language.EN
    )
    doctor = (
        await db.execute(select(DoctorProfile).where(DoctorProfile.user_id == doctor_user.id))
    ).scalar_one_or_none()
    if doctor is None:
        doctor = DoctorProfile(
            user_id=doctor_user.id, department="General Medicine",
            designation="Senior Resident", registration_number="DEMO-KMC-00000",
        )
        db.add(doctor)
        await db.flush()

    # ---------------------------------------------- Ravi — chest pain, red flag --
    ravi = await _patient(
        db, email="ravi@medikiosk.demo", name="Ravi Kumar",
        dob=date(1972, 4, 11), sex="male", language=Language.HI,
    )
    ravi_visit = await _visit(
        db, patient=ravi, complaint="Chest heaviness for three days, worse when walking",
        language=Language.HI, status=VisitStatus.INTAKE_COMPLETE, waited_minutes=12,
    )
    await _conversation(
        db, visit=ravi_visit, pathway_id="chest_pain",
        exchanges=[
            ("site", "Where exactly in your chest do you feel it?", "In the centre"),
            ("character", "What does it feel like?", "Heaviness or pressure, like something sitting on it"),
            ("onset", "When did it first start, and did it come on suddenly?", "Three days ago, it started while climbing the stairs"),
            ("duration_episode", "How long does each episode last?", "A few minutes, maybe five or ten"),
            ("aggravating", "Does anything bring it on?", "When I walk uphill or climb stairs it comes"),
            ("relieving", "Does anything make it settle down?", "If I sit and rest it goes away"),
            ("radiation", "Does the feeling move anywhere else?", "Twice it went down my left arm"),
            ("associated", "Do you also feel breathless, sweaty, or sick?", "I was sweating a lot during the worst one"),
            ("risk_factors", "Do you have diabetes, blood pressure, or a heart condition?", "Sugar since 2025 and blood pressure, I take tablets"),
            ("smoking", "Do you smoke or chew tobacco?", "I chew tobacco sometimes"),
            ("medications", "Are you taking any medicines at the moment?", "Metformin and one for BP"),
            ("red_flag_screen", "Right now, as you sit here, is the pain still there?", "No, it has settled"),
        ],
    )

    existing_flags = {
        f.rule_id
        for f in (await db.execute(select(RedFlag).where(RedFlag.visit_id == ravi_visit.id))).scalars()
    }
    for rule_id, label, detail, severity in [
        (
            "chest_exertional_radiating",
            "Chest discomfort on exertion, spreading from the chest",
            "The patient reported chest discomfort brought on by climbing stairs, and said the feeling travelled to the left arm on two occasions.",
            Severity.PRIORITY,
        ),
        (
            "cardiac_risk_context",
            "Chest symptoms alongside recorded risk factors",
            "Chest symptoms were reported by a patient who also reported diabetes since 2025 and treated high blood pressure.",
            Severity.REVIEW,
        ),
    ]:
        if rule_id not in existing_flags:
            db.add(
                RedFlag(
                    visit_id=ravi_visit.id, rule_id=rule_id, label=label, detail=detail,
                    severity=severity, source="conversation",
                    evidence=[{"key": "exertional", "category": "aggravating_factors",
                               "said": "When I walk uphill or climb stairs it comes"}],
                )
            )
    ravi_visit.priority_level = PriorityLevel.PRIORITY

    await _clinical_records(
        db, patient=ravi,
        medications=[("Metformin", "500 mg", "twice daily", date(2026, 3, 14), 0.91),
                     ("Telmisartan", "40 mg", "once daily", date(2026, 3, 14), 0.87)],
        investigations=[("HbA1c", "8.2", "%", "4.0 - 5.6", "high", date(2026, 1, 9), 0.93),
                        ("Fasting glucose", "164", "mg/dL", "70 - 100", "high", date(2026, 1, 9), 0.90)],
        history=[(HistoryType.MEDICAL, "Type 2 diabetes mellitus", "First recorded on an OPD slip; exact start date not written.", date(2025, 7, 18), True),
                 (HistoryType.MEDICAL, "Hypertension", "Noted on a prescription dated March 2026.", date(2026, 3, 14), False)],
    )
    await _summary(db, visit=ravi_visit, verified_sections={"chief_complaint"})

    # --------------------------------------- Anjali — abnormal lab, for review --
    anjali = await _patient(
        db, email="anjali@medikiosk.demo", name="Anjali Sharma",
        dob=date(1995, 9, 2), sex="female", language=Language.EN,
    )
    anjali_visit = await _visit(
        db, patient=anjali, complaint="Headache most mornings for six weeks",
        language=Language.EN, status=VisitStatus.INTAKE_COMPLETE, waited_minutes=24,
    )
    await _conversation(
        db, visit=anjali_visit, pathway_id="headache",
        exchanges=[
            ("onset", "When did the headache start?", "About six weeks ago, it built up slowly"),
            ("site", "Where in your head do you feel it?", "Both sides, like a band"),
            ("pattern", "Is it there every day, or in attacks?", "Only in the morning, most days"),
            ("associated", "Do you get anything else with the headache?", "Sometimes my vision goes blurry for a minute"),
            ("neuro_screen", "Have you had a fit, confusion, fever with neck stiffness, or a head injury?", "No, none of those"),
            ("past_history", "Have you had headaches like this before, and do you have blood pressure problems?", "Never like this before, and I have not checked my BP"),
            ("medications", "What have you been taking for it?", "Paracetamol when it is bad"),
        ],
    )
    await _clinical_records(
        db, patient=anjali, medications=[("Paracetamol", "650 mg", "as needed", None, 0.78)],
        investigations=[("Haemoglobin", "9.4", "g/dL", "12.0 - 15.0", "low", date(2026, 8, 21), 0.89)],
        history=[],
    )
    anjali_visit.priority_level = PriorityLevel.REVIEW
    if not (await db.execute(select(RedFlag).where(RedFlag.visit_id == anjali_visit.id))).scalars().all():
        db.add(
            RedFlag(
                visit_id=anjali_visit.id, rule_id="headache_focal_signs",
                label="Headache with vision change",
                detail="The patient reported brief blurring of vision alongside the headache.",
                severity=Severity.PRIORITY, source="conversation",
                evidence=[{"key": "visual_disturbance", "category": "associated_symptoms",
                           "said": "Sometimes my vision goes blurry for a minute"}],
            )
        )
        anjali_visit.priority_level = PriorityLevel.PRIORITY
    await _summary(db, visit=anjali_visit, verified_sections=set())

    # ----------------------------------------------- Kumar — routine follow-up --
    kumar = await _patient(
        db, email="kumar@medikiosk.demo", name="Kumar Swamy",
        dob=date(1959, 1, 26), sex="male", language=Language.KN,
    )
    kumar_visit = await _visit(
        db, patient=kumar, complaint="Follow-up for diabetes and blood pressure",
        language=Language.KN, status=VisitStatus.INTAKE_COMPLETE, waited_minutes=41,
    )
    await _conversation(
        db, visit=kumar_visit, pathway_id="generic",
        exchanges=[
            ("onset", "When did this start?", "I come every three months for a check"),
            ("course", "Has it been getting better, worse, or the same?", "About the same"),
            ("severity", "How much is it affecting your daily activities?", "Not much"),
            ("associated", "Have you noticed anything else?", "Nothing new"),
            ("past_history", "Do you have any long-term conditions?", "Sugar and blood pressure for twelve years"),
            ("medications", "Are you taking any medicines?", "Glimepiride and Amlodipine"),
            ("allergies", "Have you ever had a bad reaction to a medicine?", "No"),
            ("red_flag_screen", "Have you had chest pain, breathlessness, fainting or bleeding?", "No, nothing like that"),
        ],
    )
    await _clinical_records(
        db, patient=kumar,
        medications=[("Glimepiride", "2 mg", "once daily", date(2026, 6, 2), 0.94),
                     ("Amlodipine", "5 mg", "once daily", date(2026, 6, 2), 0.92)],
        investigations=[("HbA1c", "7.1", "%", "4.0 - 5.6", "high", date(2026, 6, 2), 0.95)],
        history=[(HistoryType.MEDICAL, "Type 2 diabetes mellitus", "Twelve years, per the patient.", date(2014, 1, 1), True)],
    )
    kumar_visit.priority_level = PriorityLevel.NORMAL
    await _summary(db, visit=kumar_visit, verified_sections=set())

    # ------------------------------------------ Lakshmi — document-heavy case --
    lakshmi = await _patient(
        db, email="lakshmi@medikiosk.demo", name="Lakshmi Devi",
        dob=date(1981, 11, 4), sex="female", language=Language.KN,
    )
    lakshmi_visit = await _visit(
        db, patient=lakshmi, complaint="Pain in both knees for six months",
        language=Language.KN, status=VisitStatus.INTAKE_COMPLETE, waited_minutes=53,
    )
    await _conversation(
        db, visit=lakshmi_visit, pathway_id="generic",
        exchanges=[
            ("onset", "When did this start?", "About six months back, slowly"),
            ("course", "Has it been getting better, worse, or the same?", "Getting worse"),
            ("severity", "How much is it affecting your daily activities?", "I manage with difficulty, stairs are hard"),
            ("associated", "Have you noticed anything else?", "Stiffness in the morning for about an hour"),
            ("past_history", "Do you have any long-term conditions?", "Thyroid problem, I take a tablet"),
            ("medications", "Are you taking any medicines?", "Thyroxine, and painkillers when it is bad"),
            ("allergies", "Have you ever had a bad reaction to a medicine?", "No"),
            ("red_flag_screen", "Have you had chest pain, breathlessness, fainting or bleeding?", "No"),
        ],
    )
    await _clinical_records(
        db, patient=lakshmi,
        medications=[("Thyroxine", "75 mcg", "once daily", date(2025, 11, 3), 0.9),
                     ("Diclofenac", "50 mg", "as needed", date(2026, 5, 19), 0.71)],
        investigations=[("TSH", "6.8", "mIU/L", "0.4 - 4.0", "high", date(2026, 2, 12), 0.88),
                        ("ESR", "42", "mm/hr", "0 - 20", "high", date(2026, 5, 19), 0.84),
                        ("Vitamin D", "12", "ng/mL", "30 - 100", "low", date(2026, 5, 19), 0.81)],
        history=[(HistoryType.MEDICAL, "Hypothyroidism", "On replacement since 2025.", date(2025, 11, 3), False)],
    )
    lakshmi_visit.priority_level = PriorityLevel.NORMAL
    await _summary(db, visit=lakshmi_visit, verified_sections=set())

    await db.flush()
    return {
        "doctor_login": {"email": "doctor@medikiosk.demo", "password": DEMO_PASSWORD},
        "patients": ["ravi@medikiosk.demo", "anjali@medikiosk.demo", "kumar@medikiosk.demo", "lakshmi@medikiosk.demo"],
        "password_for_all": DEMO_PASSWORD,
        "note": "All data is synthetic. No real patient information is present.",
    }


async def _clinical_records(db: AsyncSession, *, patient: PatientProfile, medications, investigations, history) -> None:
    from app.services.document_service import normalize_name

    for name, dose, frequency, started, confidence in medications:
        key = normalize_name(name)
        exists = (
            await db.execute(
                select(Medication).where(Medication.patient_id == patient.id, Medication.normalized_name == key)
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(
            Medication(
                patient_id=patient.id, name=name, normalized_name=key, dose=dose, frequency=frequency,
                started_on=started, provenance=Provenance.DOCUMENT_EXTRACTED, confidence=confidence,
                source_document_ids=[], source_count=1,
            )
        )

    for name, value, unit, reference, flag, performed, confidence in investigations:
        key = normalize_name(name)
        exists = (
            await db.execute(
                select(Investigation).where(
                    Investigation.patient_id == patient.id,
                    Investigation.normalized_name == key,
                    Investigation.performed_on == performed,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(
            Investigation(
                patient_id=patient.id, name=name, normalized_name=key, value=value, unit=unit,
                reference_range=reference, abnormal_flag=flag, performed_on=performed,
                provenance=Provenance.DOCUMENT_EXTRACTED, confidence=confidence, source_document_ids=[],
            )
        )

    for history_type, label, detail, onset, uncertain in history:
        exists = (
            await db.execute(
                select(MedicalHistoryEntry).where(
                    MedicalHistoryEntry.patient_id == patient.id, MedicalHistoryEntry.label == label
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(
            MedicalHistoryEntry(
                patient_id=patient.id, history_type=history_type, label=label, detail=detail,
                onset_date=onset, date_uncertain=uncertain, provenance=Provenance.DOCUMENT_EXTRACTED,
            )
        )
    await db.flush()


async def _summary(db: AsyncSession, *, visit: Visit, verified_sections: set[str]) -> None:
    """
    Draft summaries only, with one section pre-accepted on Ravi so the doctor
    dashboard shows a mix of states rather than a uniform wall of drafts.
    """
    from app.services.summary_service import EMPTY, SECTIONS

    exists = (
        await db.execute(select(ClinicalSummary).where(ClinicalSummary.visit_id == visit.id))
    ).scalar_one_or_none()
    if exists:
        return

    summary = ClinicalSummary(
        visit_id=visit.id, status=VerificationState.DRAFT, generated_by="seed",
        generated_at=datetime.now(UTC),
    )
    db.add(summary)
    await db.flush()

    for order, (key, label, provenance) in enumerate(SECTIONS):
        verified = key in verified_sections
        db.add(
            SummarySection(
                summary_id=summary.id, key=key, label=label, display_order=order,
                ai_body=EMPTY[key] if key not in ("chief_complaint",) else (visit.chief_complaint or EMPTY[key]),
                provenance=Provenance.DOCTOR_VERIFIED if verified else provenance,
                status=VerificationState.VERIFIED if verified else VerificationState.DRAFT,
            )
        )
    await db.flush()


async def main() -> None:
    async with SessionLocal() as db:
        result = await seed(db)
        await db.commit()
    print("Seeded. Sign in with:")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        print(f"Seeding stopped: {exc}", file=sys.stderr)
        sys.exit(1)
