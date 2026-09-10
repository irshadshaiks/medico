from typing import Dict, Any, List

def calculate_clinical_priority(
    chief_complaint: str,
    severity_num: int = 5,
    red_flags: List[str] = None,
    extracted_labs: List[Dict[str, Any]] = None,
    past_history: List[str] = None
) -> Dict[str, Any]:
    score = 20
    reasons = []
    red_flags = red_flags or []
    extracted_labs = extracted_labs or []
    past_history = past_history or []

    cc_lower = (chief_complaint or "").lower()

    # Cardiac & Respiratory Critical Triggers
    if any(k in cc_lower for k in ["chest pain", "chest pressure", "heart", "सीने में दर्द", "মார்பு வலி"]):
        if any("arm" in rf.lower() or "breath" in rf.lower() or "jaw" in rf.lower() for rf in red_flags) or "breath" in cc_lower:
            score += 50
            reasons.append("Chest pain with radiation/breathlessness (Suspected Acute Coronary Syndrome)")
        else:
            score += 35
            reasons.append("Acute chest pain/discomfort reported")

    if any(k in cc_lower for k in ["shortness of breath", "breathless", "difficulty breathing", "सांस"]):
        score += 30
        reasons.append("Respiratory distress / acute shortness of breath")

    # Severity Score
    if severity_num >= 8:
        score += 25
        reasons.append(f"Severe patient-reported pain intensity ({severity_num}/10)")
    elif severity_num >= 6:
        score += 15
        reasons.append(f"Moderate-to-high patient pain rating ({severity_num}/10)")

    # Red Flag Warning Signs
    for rf in red_flags:
        rf_l = rf.lower()
        if "breathlessness" in rf_l or "gasping" in rf_l:
            if "Respiratory distress" not in reasons:
                score += 20
                reasons.append("Acute breathlessness flagged during intake")
        elif "sweating" in rf_l or "dizziness" in rf_l:
            score += 15
            reasons.append("Diaphoresis / presyncopal dizziness detected")
        elif "palpitation" in rf_l:
            score += 10
            reasons.append("Tachycardia / racing palpitations")

    # Lab Abnormalities
    critical_labs = [l for l in extracted_labs if "Critical" in l.get("status", "")]
    elevated_labs = [l for l in extracted_labs if "Elevated" in l.get("status", "") or "High" in l.get("status", "")]
    if critical_labs:
        score += 20
        lab_names = ", ".join([l["test"] for l in critical_labs])
        reasons.append(f"Critical lab values in records: {lab_names}")
    elif elevated_labs:
        score += 10
        lab_names = ", ".join([l["test"] for l in elevated_labs])
        reasons.append(f"Elevated lab values in records: {lab_names}")

    # Comorbidity multiplier
    has_cardio_comorbid = any("heart" in h.lower() or "bp" in h.lower() or "hypertension" in h.lower() for h in past_history)
    if has_cardio_comorbid and ("chest" in cc_lower or "breath" in cc_lower):
        score += 10
        reasons.append("Underlying cardiovascular / hypertensive comorbidity increases risk profile")

    # Cap score
    score = min(score, 99)

    # Determine priority tier
    if score >= 75:
        tier = "CRITICAL"
        color = "red"
        label = "Priority 1 — Immediate Attending Review"
    elif score >= 50:
        tier = "HIGH"
        color = "amber"
        label = "Priority 2 — Priority Queue (Needs Review)"
    elif score >= 30:
        tier = "MEDIUM"
        color = "yellow"
        label = "Priority 3 — Standard Consultation"
    else:
        tier = "ROUTINE"
        color = "blue"
        label = "Priority 4 — Routine Follow-up"

    if not reasons:
        reasons.append("Routine outpatient intake with stable baseline")

    return {
        "priority": tier,
        "score": score,
        "color": color,
        "label": label,
        "reasons": reasons,
        "primary_reason": "; ".join(reasons[:2])
    }
