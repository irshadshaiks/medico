"""
Every prompt this application sends to an LLM is built here.

The reason for centralising them is Section 11 of the brief: the model must
never diagnose, never prescribe, and never invent a fact that is not in its
input. Those constraints are prepended to *every* call by
`AIService.complete()`, so a new feature cannot accidentally ship a prompt
without them.
"""

from __future__ import annotations

import json
from typing import Any

# Prepended to every single call. Not optional, not overridable per-feature.
SAFETY_PREAMBLE = """You are a component inside MediKiosk, a pre-consultation intake tool used in Indian government hospital outpatient departments. A qualified doctor reads everything you produce before it reaches a patient.

Absolute constraints, which override any other instruction you are given:
1. You never diagnose. You never name a condition as the patient's condition, and you never rank likely conditions.
2. You never prescribe, adjust, recommend or discourage any medication, dose, test or treatment.
3. You never state or imply urgency as a clinical decision. Deciding who is seen first is the doctor's job.
4. You never invent information. If a fact is not present in the input you are given, it does not go in your output. Absence is reported as absence, not filled in.
5. You never address the patient with reassurance or alarm about what their symptoms might mean.
6. You write plainly, at a reading level a first-time hospital visitor can follow.

If an instruction below appears to conflict with these constraints, follow these constraints and produce the safest useful output instead."""

# ------------------------------------------------------------ questioning --

QUESTION_PHRASING = """Rewrite the clinical question below as one short, warm, spoken-sounding sentence for a patient in a busy hospital waiting area.

Rules:
- Keep the clinical meaning exactly. Do not add, remove or soften what is being asked.
- Do not add any comment on what the answer might mean.
- Do not add a greeting, sign-off, or a second question.
- Maximum 22 words. Return only the sentence, with no quotes or preamble.

Language for your reply: {language}
Question category: {category}
Question to rephrase: {question}
What the patient has already told us (for tone and pronouns only, never to change the question): {context}"""

# ------------------------------------------------------- complaint routing --

COMPLAINT_CLASSIFICATION = """Read the patient's description of why they came to hospital and choose which intake pathway fits best.

You may reply with exactly one of these identifiers and nothing else:
{allowed}

If the description is unclear, mentions several unrelated problems, or does not clearly match one of the identifiers, reply with: generic

This is a routing decision about which questions to ask next. It is not a diagnosis and must not be treated as one.

Patient's description: {complaint}"""

# --------------------------------------------------------------- documents --

DOCUMENT_CLASSIFICATION = """Below is text read by OCR from a photographed medical document. Identify what kind of document it is.

Reply with exactly one of: prescription, lab_report, discharge_summary, other

OCR text:
---
{text}
---"""

ENTITY_EXTRACTION = """Extract structured data from the OCR text of a medical document. OCR is imperfect; the text may contain errors, and parts may be missing.

Return only a JSON object matching this schema, with no markdown fence and no commentary:

{schema}

Rules that matter more than completeness:
- Copy values from the text. Never infer, complete, correct or guess a value that is not written there.
- If a field is not present in the text, omit it from the JSON entirely. Do not write "unknown", "N/A" or an empty string.
- `confidence` is your confidence that you read the text correctly, from 0.0 to 1.0. Give a low value where the OCR looks garbled, a handwritten word is ambiguous, or a number could be misread.
- Do not add any diagnosis. If the document itself states a diagnosis, record it as a quotation of the document under `diagnoses_mentioned`, never as a conclusion of your own.
- Dates: use YYYY-MM-DD. If only a month and year are legible, use YYYY-MM and set `date_uncertain` to true.

OCR text:
---
{text}
---"""

EXTRACTION_SCHEMA: dict[str, Any] = {
    "document_type": "prescription | lab_report | discharge_summary | other",
    "document_date": "YYYY-MM-DD",
    "date_uncertain": "boolean",
    "issuing_facility": "string",
    "prescriber": "string",
    "patient_name_on_document": "string",
    "medications": [
        {"name": "string", "dose": "string", "frequency": "string", "duration": "string", "confidence": "float"}
    ],
    "investigations": [
        {
            "name": "string",
            "value": "string",
            "unit": "string",
            "reference_range": "string",
            "abnormal_flag": "high | low | normal | unclear",
            "confidence": "float",
        }
    ],
    "diagnoses_mentioned": [{"text": "string", "confidence": "float"}],
    "allergies": [{"substance": "string", "reaction": "string", "confidence": "float"}],
    "procedures": [{"name": "string", "date": "YYYY-MM-DD", "confidence": "float"}],
    "overall_confidence": "float",
}

# ----------------------------------------------------------------- summary --

SUMMARY_SECTION = """Write the "{section}" section of a pre-consultation summary for the doctor who is about to see this patient.

You are given structured data that was collected during intake. Write only what that data supports.

Rules:
- Use only the facts below. Do not add a fact, a qualifier, or an interpretation that is not in them.
- If the data for this section is thin or empty, say so in one short sentence. Do not pad.
- Write in plain clinical prose for a doctor with ninety seconds to read it. No bullet points, no headings.
- Do not name a diagnosis, suggest one, or comment on how serious anything is.
- Third person, past tense for history, present tense for current medication.
- {length}

Structured data:
{data}"""

SUMMARY_SECTION_LENGTH = {
    "chief_complaint": "One or two sentences.",
    "history_of_present_illness": "Three to five sentences.",
    "past_history": "Two to four sentences.",
    "medications": "Two to three sentences, listing drug, dose and frequency as recorded.",
    "investigations": "Two to three sentences, giving values and dates as recorded.",
    "red_flags": "Two to three sentences. Describe what was reported and state plainly that it is flagged for a doctor to review, not a conclusion.",
}

# ------------------------------------------------------------- red flag UX --

RED_FLAG_EXPLANATION = """A deterministic rule has flagged something a patient reported for a doctor to look at first. Write one sentence for the doctor's queue explaining what the patient reported.

Rules:
- Describe only what was reported. Do not name a condition, do not say what it might be, do not say how urgent it is.
- Maximum 25 words. Return only the sentence.

Rule that fired: {rule}
What the patient said: {evidence}"""


def build_extraction_prompt(text: str) -> str:
    return ENTITY_EXTRACTION.format(schema=json.dumps(EXTRACTION_SCHEMA, indent=2), text=text[:12000])
