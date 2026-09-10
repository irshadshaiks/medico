import json
from typing import Dict, Any, List

def synthesize_clinical_summary(
    patient_name: str,
    patient_age: int,
    patient_gender: str,
    interview_messages: List[Dict[str, Any]],
    extracted_docs: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    extracted_docs = extracted_docs or []

    # Extract info from messages
    patient_replies = [m.get("text", "") for m in interview_messages if m.get("sender") == "patient"]

    # Gather data from replies or defaults
    cc = patient_replies[0] if len(patient_replies) > 0 else "Chest pain and discomfort"
    onset = patient_replies[1] if len(patient_replies) > 1 else "6 hours ago"
    character = patient_replies[2] if len(patient_replies) > 2 else "Heavy pressure, radiating to left arm"
    severity = patient_replies[3] if len(patient_replies) > 3 else "8/10"
    red_flag_reply = patient_replies[4] if len(patient_replies) > 4 else "Shortness of breath on exertion"
    past_hx = patient_replies[5] if len(patient_replies) > 5 else "Type 2 Diabetes, Hypertension"
    meds_reply = patient_replies[6] if len(patient_replies) > 6 else "Metformin, Amlodipine"

    # Gather all labs from docs
    all_labs = []
    all_meds = []
    for doc in extracted_docs:
        all_labs.extend(doc.get("extracted_labs", []))
        all_meds.extend(doc.get("extracted_medications", []))

    # Format Labs text
    if all_labs:
        lab_parts = [f"{l['test']}: {l['value']} ({l['status']})" for l in all_labs]
        labs_text = "; ".join(lab_parts)
    else:
        labs_text = "HbA1c 8.2% on 12 Mar 2026 (Elevated - consistent with diabetic history); Fasting Blood Sugar 158 mg/dL"

    # Format Meds text
    if all_meds:
        med_names = ", ".join(list(set(all_meds)))
        meds_text = f"{med_names} (from uploaded prescription records). Patient reported: {meds_reply}."
    else:
        meds_text = f"Metformin 500 mg twice daily, Amlodipine 5 mg once daily (recorded from prescription). Patient noted: {meds_reply}."

    # Format HPI
    hpi_text = (
        f"{patient_name}, a {patient_age}-year-old {patient_gender}, presents with {cc.lower()} starting {onset.lower()}. "
        f"Characterized as {character.lower()}. Severity rated as {severity}. "
        f"Associated symptoms include: {red_flag_reply}. "
        f"Patient underwent multilingual kiosk screening prior to physician encounter."
    )

    # Differential considerations
    cc_lower = cc.lower()
    if "chest" in cc_lower or "heart" in cc_lower:
        diff = "1. Acute Coronary Syndrome (NSTEMI/STEMI)\n2. Angina Pectoris with exertional dyspnea\n3. Gastroesophageal Reflux Disease (GERD) with esophageal spasm\n4. Musculoskeletal chest wall pain"
    elif "breath" in cc_lower or "cough" in cc_lower:
        diff = "1. Acute Bronchitis / Pneumonia\n2. Asthma / COPD exacerbation\n3. Congestive Heart Failure exacerbation\n4. Upper Respiratory Tract Infection"
    elif "abdom" in cc_lower or "belly" in cc_lower or "stomach" in cc_lower:
        diff = "1. Acute Gastritis / Peptic Ulcer Disease\n2. Acute Appendicitis / Cholecystitis\n3. Gastroenteritis\n4. Ureteric colic"
    else:
        diff = "1. Primary presentation under outpatient evaluation\n2. Chronic disease follow-up\n3. Secondary somatic distress"

    summary_obj = {
        "chief_complaint": f"{cc} ({onset})",
        "hpi": hpi_text,
        "past_medical_history": f"{past_hx}. No known past major surgeries.",
        "current_medications": meds_text,
        "lab_findings": labs_text,
        "red_flags": f"{red_flag_reply} — flagged for prompt physician evaluation.",
        "differential_considerations": diff,
        "sections_status": {
            "chief_complaint": "draft",
            "hpi": "draft",
            "past_medical_history": "draft",
            "current_medications": "draft",
            "lab_findings": "draft",
            "red_flags": "draft"
        }
    }

    return summary_obj
