"""
Deterministic stand-in for the LLM.

This is the default provider. It exists so the whole application — tests, CI, a
teammate with no API key, a demo with no network — runs end to end without a
single paid call, and so nothing downstream is allowed to assume a live model.
Its answers are canned and safe by construction.
"""

from __future__ import annotations

import json
import re

from app.services.ai.base import AICompletionRequest, BaseAIService


class MockAIService(BaseAIService):
    name = "mock"

    async def _call(self, system: str, prompt: str, req: AICompletionRequest) -> str:
        # Routing: reply with a pathway id the classifier will accept.
        if "choose which intake pathway" in prompt:
            lowered = prompt.lower()
            for needle, pathway in (
                ("chest", "chest_pain"),
                ("breath", "respiratory"),
                ("cough", "respiratory"),
                ("fever", "fever"),
                ("stomach", "abdominal_pain"),
                ("abdomen", "abdominal_pain"),
                ("pet", "abdominal_pain"),
                ("headache", "headache"),
                ("sir dard", "headache"),
            ):
                if needle in lowered:
                    return pathway
            return "generic"

        if "Identify what kind of document" in prompt:
            lowered = prompt.lower()
            if "tab." in lowered or "rx" in lowered or "mg" in lowered and "prescri" in lowered:
                return "prescription"
            if "hba1c" in lowered or "reference" in lowered or "result" in lowered:
                return "lab_report"
            if "discharge" in lowered:
                return "discharge_summary"
            return "other"

        if "Extract structured data" in prompt:
            return json.dumps(_mock_extraction(prompt))

        if "Rewrite the clinical question" in prompt:
            # Hand the canonical question straight back — safe, and it makes the
            # phrasing step a no-op rather than a source of drift in tests.
            match = re.search(r"Question to rephrase:\s*(.+?)(?:\n|$)", prompt)
            return match.group(1).strip() if match else "Could you tell me a little more?"

        if "Write one sentence for the doctor's queue" in prompt:
            match = re.search(r"What the patient said:\s*(.+?)(?:\n|$)", prompt, re.DOTALL)
            said = (match.group(1).strip() if match else "")[:120]
            return f"The patient reported: {said}"

        if 'section of a pre-consultation summary' in prompt:
            return _mock_summary(prompt)

        return "This response was produced by the offline mock provider."


def _mock_extraction(prompt: str) -> dict:
    text = prompt.lower()
    out: dict = {"document_type": "other", "overall_confidence": 0.72, "medications": [], "investigations": []}
    if "metformin" in text:
        out["document_type"] = "prescription"
        out["medications"].append(
            {"name": "Metformin", "dose": "500 mg", "frequency": "twice daily", "confidence": 0.91}
        )
    if "telmisartan" in text:
        out["document_type"] = "prescription"
        out["medications"].append(
            {"name": "Telmisartan", "dose": "40 mg", "frequency": "once daily", "confidence": 0.87}
        )
    if "hba1c" in text:
        out["document_type"] = "lab_report"
        out["investigations"].append(
            {
                "name": "HbA1c", "value": "8.2", "unit": "%", "reference_range": "4.0-5.6",
                "abnormal_flag": "high", "confidence": 0.93,
            }
        )
    date = re.search(r"(\d{4}-\d{2}-\d{2})", prompt)
    if date:
        out["document_date"] = date.group(1)
    return out


def _mock_summary(prompt: str) -> str:
    section = re.search(r'the "(.+?)" section', prompt)
    key = section.group(1) if section else "summary"
    canned = {
        "chief_complaint": "The patient reported the complaint recorded during intake.",
        "history_of_present_illness": "The patient described the course of the current problem during intake. Details are recorded in the structured responses above.",
        "past_history": "Past history was recorded from the patient's answers and any documents uploaded during intake.",
        "medications": "Current medication as recorded during intake and from uploaded prescriptions.",
        "investigations": "Previous investigation results as read from the uploaded reports.",
        "red_flags": "One or more responses matched a rule and were flagged for a doctor to review first. No clinical conclusion has been drawn.",
    }
    return canned.get(key, "No data was available for this section during intake.")
