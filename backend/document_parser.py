import re
import os
import json
from datetime import datetime
from typing import Dict, Any, List

def parse_pdf_text(file_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error parsing PDF with pypdf: {e}")
        return ""

LAB_TEST_PATTERNS = [
    {
        "test": "HbA1c (Glycated Hemoglobin)",
        "pattern": r"(?:hba1c|glycated\s+hemoglobin|a1c)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*%",
        "unit": "%",
        "normal_range": "< 5.7%",
        "high_threshold": 6.5,
        "critical_threshold": 8.0
    },
    {
        "test": "Fasting Blood Glucose (FBS)",
        "pattern": r"(?:fasting\s+blood\s+(?:sugar|glucose)|fbs)[\s:]*([0-9]{2,3})\s*(?:mg/dl)?",
        "unit": "mg/dL",
        "normal_range": "70 - 100 mg/dL",
        "high_threshold": 126,
        "critical_threshold": 200
    },
    {
        "test": "Postprandial Blood Glucose (PPBS)",
        "pattern": r"(?:post\s*prandial|ppbs|random\s+blood\s+(?:sugar|glucose)|rbs)[\s:]*([0-9]{2,3})\s*(?:mg/dl)?",
        "unit": "mg/dL",
        "normal_range": "< 140 mg/dL",
        "high_threshold": 200,
        "critical_threshold": 280
    },
    {
        "test": "Serum Creatinine",
        "pattern": r"(?:serum\s+creatinine|creatinine)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*(?:mg/dl)?",
        "unit": "mg/dL",
        "normal_range": "0.7 - 1.3 mg/dL",
        "high_threshold": 1.4,
        "critical_threshold": 2.2
    },
    {
        "test": "Blood Urea",
        "pattern": r"(?:blood\s+urea|urea)[\s:]*([0-9]{1,3})\s*(?:mg/dl)?",
        "unit": "mg/dL",
        "normal_range": "15 - 45 mg/dL",
        "high_threshold": 50,
        "critical_threshold": 80
    },
    {
        "test": "Hemoglobin (Hb)",
        "pattern": r"(?:hemoglobin|hb|haemoglobin)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*(?:g/dl|gm/dl)?",
        "unit": "g/dL",
        "normal_range": "13.0 - 17.0 g/dL",
        "low_threshold": 11.0,
        "critical_threshold": 8.0
    },
    {
        "test": "Total Leucocyte Count (TLC/WBC)",
        "pattern": r"(?:total\s+leucocyte\s+count|tlc|wbc)[\s:]*([0-9]{3,5})\s*(?:/cumm)?",
        "unit": "/cumm",
        "normal_range": "4,000 - 11,000 /cumm",
        "high_threshold": 11000,
        "critical_threshold": 15000
    },
    {
        "test": "Total Cholesterol",
        "pattern": r"(?:total\s+cholesterol|cholesterol)[\s:]*([0-9]{2,3})\s*(?:mg/dl)?",
        "unit": "mg/dL",
        "normal_range": "< 200 mg/dL",
        "high_threshold": 200,
        "critical_threshold": 240
    },
    {
        "test": "Blood Pressure (BP)",
        "pattern": r"(?:blood\s+pressure|bp)[\s:]*([0-9]{2,3})\s*/\s*([0-9]{2,3})\s*(?:mmhg)?",
        "unit": "mmHg",
        "normal_range": "< 120/80 mmHg",
        "is_bp": True
    }
]

MEDICATION_PATTERNS = [
    r"(metformin\s*(?:\d+\s*mg)?)",
    r"(glimepiride\s*(?:\d+\s*mg)?)",
    r"(amlodipine\s*(?:\d+\s*mg)?)",
    r"(telmisartan\s*(?:\d+\s*mg)?)",
    r"(losartan\s*(?:\d+\s*mg)?)",
    r"(atorvastatin\s*(?:\d+\s*mg)?)",
    r"(rosuvastatin\s*(?:\d+\s*mg)?)",
    r"(aspirin\s*(?:\d+\s*mg)?)",
    r"(clopidogrel\s*(?:\d+\s*mg)?)",
    r"(pantoprazole\s*(?:\d+\s*mg)?)",
    r"(paracetamol\s*(?:\d+\s*mg)?)",
    r"(amoxicillin\s*(?:\d+\s*mg)?)",
    r"(azithromycin\s*(?:\d+\s*mg)?)",
    r"(salbutamol\s*(?:\d+\s*mg|inhaler)?)",
    r"(montelukast\s*(?:\d+\s*mg)?)"
]

def extract_entities_from_text(raw_text: str, filename: str = "document.pdf") -> Dict[str, Any]:
    text_lower = raw_text.lower()
    extracted_labs: List[Dict[str, Any]] = []
    extracted_meds: List[str] = []
    abnormal_count = 0
    confidence = 0.94 if len(raw_text) > 100 else 0.85

    # Extract dates
    dates_found = re.findall(r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b", raw_text, re.IGNORECASE)
    doc_date = dates_found[0] if dates_found else "Recent (2025/2026)"

    # Extract labs
    for lab_def in LAB_TEST_PATTERNS:
        match = re.search(lab_def["pattern"], text_lower)
        if match:
            if lab_def.get("is_bp"):
                sys = int(match.group(1))
                dia = int(match.group(2))
                val_str = f"{sys}/{dia} {lab_def['unit']}"
                status = "Normal"
                if sys >= 180 or dia >= 110:
                    status = "Critical High (Crisis)"
                    abnormal_count += 2
                elif sys >= 140 or dia >= 90:
                    status = "High (Stage 2 HTN)"
                    abnormal_count += 1
                extracted_labs.append({
                    "test": lab_def["test"],
                    "value": val_str,
                    "numeric_value": sys,
                    "unit": lab_def["unit"],
                    "status": status,
                    "reference": lab_def["normal_range"]
                })
            else:
                num_val = float(match.group(1))
                val_str = f"{num_val} {lab_def['unit']}"
                status = "Normal"
                if "critical_threshold" in lab_def and num_val >= lab_def["critical_threshold"]:
                    status = "Critical High"
                    abnormal_count += 2
                elif "high_threshold" in lab_def and num_val >= lab_def["high_threshold"]:
                    status = "Elevated"
                    abnormal_count += 1
                elif "low_threshold" in lab_def and num_val <= lab_def["low_threshold"]:
                    status = "Low (Subnormal)"
                    abnormal_count += 1

                extracted_labs.append({
                    "test": lab_def["test"],
                    "value": val_str,
                    "numeric_value": num_val,
                    "unit": lab_def["unit"],
                    "status": status,
                    "reference": lab_def["normal_range"]
                })

    # Extract meds
    for med_pat in MEDICATION_PATTERNS:
        med_matches = re.findall(med_pat, text_lower)
        for m in med_matches:
            title_m = m.title().strip()
            if title_m not in extracted_meds:
                extracted_meds.append(title_m)

    # Document type detection
    doc_type = "Medical Record"
    if "prescription" in text_lower or "rx" in text_lower or "tablet" in text_lower:
        doc_type = "Prescription"
    elif "pathology" in text_lower or "laboratory" in text_lower or "investigation" in text_lower or "hba1c" in text_lower:
        doc_type = "Diagnostic Lab Report"
    elif "ecg" in text_lower or "electrocardiogram" in text_lower:
        doc_type = "ECG Report"

    return {
        "filename": filename,
        "doc_type": doc_type,
        "date_detected": doc_date,
        "confidence": confidence,
        "extracted_labs": extracted_labs,
        "extracted_medications": extracted_meds,
        "abnormal_findings_count": abnormal_count,
        "summary_snippet": raw_text[:300] + "..." if len(raw_text) > 300 else raw_text
    }
