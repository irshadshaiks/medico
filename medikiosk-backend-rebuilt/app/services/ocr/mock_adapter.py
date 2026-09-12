"""
Offline OCR stand-in.

Returns one of the seeded synthetic documents so the extraction pipeline,
normalization and timeline can all be exercised with no Tesseract binary
present. Every string here is fabricated for the demo.
"""

from __future__ import annotations

from app.services.ocr.base import OCRResult, OCRService

PRESCRIPTION = """DISTRICT GOVERNMENT HOSPITAL
OUT PATIENT DEPARTMENT

Patient: Ravi Kumar        Age: 54 / M
Date: 2026-03-14           OPD No: 20260314-1187

Rx
1. Tab. Metformin 500 mg  -  1 tablet twice daily after food
2. Tab. Telmisartan 40 mg -  1 tablet once daily morning

Known case of Type 2 Diabetes Mellitus and Hypertension.
Review after 3 months.

Dr. S. Rao, MBBS MD (Gen. Med.)
"""

LAB_REPORT = """DISTRICT HOSPITAL CENTRAL LABORATORY
BIOCHEMISTRY REPORT

Name: Ravi Kumar          Age/Sex: 54 Y / M
Collected: 2026-01-09     Reported: 2026-01-09

TEST                 RESULT     UNIT      REFERENCE
HbA1c                8.2        %         4.0 - 5.6
Fasting Glucose      164        mg/dL     70 - 100
Serum Creatinine     0.9        mg/dL     0.7 - 1.3

* Values outside the reference range are marked by the analyser.
"""


class MockOCRService(OCRService):
    name = "mock"

    async def extract_text(self, data: bytes, mime_type: str, languages: str | None = None) -> OCRResult:
        # Deterministic on the file bytes, so re-uploading the same file gives
        # the same document every time.
        text = LAB_REPORT if (len(data) % 2 == 0) else PRESCRIPTION
        return OCRResult(text=text, confidence=0.88, provider=self.name, page_count=1)
