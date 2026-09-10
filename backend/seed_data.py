import json
import uuid
from datetime import datetime, timedelta
from database import get_db, init_db
from auth import hash_password

def seed_database():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Clear existing data for fresh clean seed
    cursor.execute("DELETE FROM audit_logs")
    cursor.execute("DELETE FROM clinical_summaries")
    cursor.execute("DELETE FROM documents")
    cursor.execute("DELETE FROM interview_messages")
    cursor.execute("DELETE FROM cases")
    cursor.execute("DELETE FROM users")

    now = datetime.now()
    t_11m = (now - timedelta(minutes=11)).isoformat()
    t_25m = (now - timedelta(minutes=25)).isoformat()
    t_40m = (now - timedelta(minutes=40)).isoformat()
    t_1h = (now - timedelta(hours=1, minutes=15)).isoformat()

    # 1. Users
    doctor_id = "doc-menon-001"
    cursor.execute('''
    INSERT INTO users (id, email, password_hash, full_name, role, phone, age, gender, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        doctor_id,
        "doctor@medikiosk.in",
        hash_password("doctor123"),
        "Dr. A. Menon",
        "doctor",
        "+91 98765 43210",
        45,
        "Male",
        now.isoformat()
    ))

    patient1_id = "pat-ravi-001"
    cursor.execute('''
    INSERT INTO users (id, email, password_hash, full_name, role, phone, age, gender, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        patient1_id,
        "ravi.kumar@example.com",
        hash_password("patient123"),
        "Ravi Kumar",
        "patient",
        "+91 98111 22233",
        54,
        "Male",
        t_11m
    ))

    # 2. Case 1: Ravi Kumar (Priority / Chest Pain & Breathlessness - exact match with landing page demo!)
    case1_id = "case-rk-001"
    cursor.execute('''
    INSERT INTO cases (id, patient_id, patient_name, patient_age, patient_gender, language, chief_complaint, status, priority, priority_score, priority_reason, consent_given, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case1_id,
        patient1_id,
        "Ravi Kumar",
        54,
        "Male",
        "en",
        "Central chest pain since 06:00, radiating to left arm with breathlessness on exertion",
        "submitted",
        "CRITICAL",
        88,
        "Suspected Acute Coronary Syndrome; breathlessness reported with crushing chest pain; severe rating (8/10); underlying Type 2 DM and HTN",
        1,
        t_11m,
        t_11m
    ))

    # Messages for Case 1
    messages_c1 = [
        ("ai", "Namaste and welcome. I am MediKiosk, your pre-consultation assistant. To help the doctor understand your condition thoroughly, what is the primary health issue or discomfort you are experiencing today?", ["Chest Pain / Pressure", "Shortness of Breath"]),
        ("patient", "Central chest pain since this morning around 06:00, feels like heavy tight pressure.", None),
        ("ai", "When did this discomfort start, and is it constant or coming in waves?", ["Constant severe ache", "Comes and goes"]),
        ("patient", "Constant heavy pressure for the past 6 hours, radiating to my left arm and shoulder.", None),
        ("ai", "On a pain scale from 1 to 10, how severe is it right now?", ["8-9/10 - Very severe", "10/10 - Emergency"]),
        ("patient", "It is 8/10, very painful. Also feeling breathless when walking.", None),
        ("ai", "Do you have any known existing medical conditions or chronic illnesses?", ["Type 2 Diabetes", "Hypertension"]),
        ("patient", "Yes, diagnosed with Type 2 Diabetes and Hypertension for 4 years.", None),
        ("ai", "What medicines are you taking regularly?", ["Metformin", "Amlodipine"]),
        ("patient", "Taking Metformin 500 mg twice daily and Amlodipine 5 mg once daily.", None),
        ("ai", "Please upload or snap a photo of any recent lab test reports or prescriptions you brought with you.", ["Prescription 2025", "Lab Report 12 Mar 2026"]),
        ("patient", "Uploaded 2025 Prescription and Recent Blood Test from 12 Mar 2026.", None)
    ]

    for sender, text, opts in messages_c1:
        cursor.execute('''
        INSERT INTO interview_messages (id, case_id, sender, text, options_json, timestamp, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            case1_id,
            sender,
            text,
            json.dumps(opts) if opts else None,
            t_11m,
            None
        ))

    # Documents for Case 1
    doc1_id = "doc-rk-rx"
    cursor.execute('''
    INSERT INTO documents (id, case_id, filename, file_path, file_type, extracted_text, structured_data_json, uploaded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        doc1_id,
        case1_id,
        "Prescription_Oct2025.pdf",
        "/uploads/Prescription_Oct2025.pdf",
        "application/pdf",
        "Rx: Tab Metformin 500mg BD after meals. Tab Amlodipine 5mg OD morning. Patient diagnosed with T2DM and Essential HTN.",
        json.dumps({
            "doc_type": "Prescription",
            "date_detected": "15 Oct 2025",
            "extracted_medications": ["Metformin 500 mg", "Amlodipine 5 mg"],
            "extracted_labs": [{"test": "Blood Pressure (BP)", "value": "148/92 mmHg", "status": "Elevated", "reference": "< 120/80 mmHg"}]
        }),
        t_11m
    ))

    doc2_id = "doc-rk-lab"
    cursor.execute('''
    INSERT INTO documents (id, case_id, filename, file_path, file_type, extracted_text, structured_data_json, uploaded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        doc2_id,
        case1_id,
        "Diagnostic_Report_12Mar2026.pdf",
        "/uploads/Diagnostic_Report_12Mar2026.pdf",
        "application/pdf",
        "Metropolis Pathology Lab - 12 Mar 2026. HbA1c Glycated Hemoglobin: 8.2% (High). Fasting Blood Glucose: 168 mg/dL. Serum Creatinine: 1.1 mg/dL.",
        json.dumps({
            "doc_type": "Diagnostic Lab Report",
            "date_detected": "12 Mar 2026",
            "confidence": 0.94,
            "extracted_medications": [],
            "extracted_labs": [
                {"test": "HbA1c (Glycated Hemoglobin)", "value": "8.2 %", "status": "Critical High", "reference": "< 5.7%"},
                {"test": "Fasting Blood Glucose (FBS)", "value": "168 mg/dL", "status": "Elevated", "reference": "70 - 100 mg/dL"},
                {"test": "Serum Creatinine", "value": "1.1 mg/dL", "status": "Normal", "reference": "0.7 - 1.3 mg/dL"}
            ]
        }),
        t_11m
    ))

    # Clinical Summary for Case 1
    cursor.execute('''
    INSERT INTO clinical_summaries (id, case_id, chief_complaint_summary, hpi, past_medical_history, current_medications, lab_findings, physical_observations, red_flags, differential_considerations, verification_status, doctor_notes, verified_sections_json, generated_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        case1_id,
        "Central chest pain, 6 hours, radiating to the left arm, with breathlessness on exertion.",
        "54-year-old male with 4-year history of Type 2 Diabetes and Hypertension presents with sudden-onset heavy retrosternal chest pain beginning at 06:00 today. Pain is radiating to left shoulder and arm. Severity rated 8/10. Accompanied by exertional dyspnea. No syncope.",
        "Type 2 diabetes noted in a 2025 prescription. Hypertension on the same script.",
        "Metformin 500 mg twice daily, Amlodipine 5 mg once daily (from uploaded Oct 2025 prescription).",
        "HbA1c 8.2% on 12 Mar 2026 (confidence 0.94); Fasting Blood Sugar 168 mg/dL; BP in clinic 148/92 mmHg.",
        "Alert, mild diaphoresis, in noticeable discomfort sitting upright.",
        "Breathlessness reported with chest pain — routed to the doctor's priority queue.",
        "1. Acute Coronary Syndrome (STEMI / NSTEMI)\n2. Unstable Angina\n3. Gastroesophageal reflux / Esophageal spasm\n4. Musculoskeletal chest wall pain",
        "draft",
        "Patient prioritized for emergency 12-lead ECG and troponin-I stat.",
        json.dumps({
            "chief_complaint": False,
            "hpi": False,
            "past_medical_history": False,
            "current_medications": False,
            "lab_findings": False,
            "red_flags": False
        }),
        t_11m,
        t_11m
    ))

    # 3. Case 2: Sunita Devi (Needs Review / High Priority)
    case2_id = "case-sd-002"
    cursor.execute('''
    INSERT INTO cases (id, patient_id, patient_name, patient_age, patient_gender, language, chief_complaint, status, priority, priority_score, priority_reason, consent_given, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case2_id,
        None,
        "Sunita Devi",
        48,
        "Female",
        "hi",
        "धुंधला दिखना, अत्यधिक प्यास और कमजोरी (Uncontrolled hyperglycemia & lethargy)",
        "submitted",
        "HIGH",
        64,
        "Severe hyperglycemia symptoms (Fasting Glucose 242 mg/dL); blurred vision; uncontrolled diabetic progression",
        1,
        t_25m,
        t_25m
    ))

    cursor.execute('''
    INSERT INTO clinical_summaries (id, case_id, chief_complaint_summary, hpi, past_medical_history, current_medications, lab_findings, physical_observations, red_flags, differential_considerations, verification_status, doctor_notes, verified_sections_json, generated_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        case2_id,
        "Blurred vision and profound lethargy over 2 weeks with polydipsia.",
        "48-year-old female presents with progressive polyuria, polydipsia and blurred vision. No fever, no chest pain.",
        "Known Type 2 Diabetes for 6 years, irregular compliance with oral medication.",
        "Glimepiride 1 mg once daily (self-reported, stopped 3 weeks ago).",
        "Fasting Blood Sugar: 242 mg/dL (Critical High); Urine Ketones: Negative.",
        "Dehydrated oral mucosa, hemodynamically stable.",
        "Marked hyperglycemia with visual blurriness — rule out hyperosmolar state / diabetic retinopathy.",
        "1. Uncontrolled Type 2 Diabetes Mellitus with severe hyperglycemia\n2. Diabetic Retinopathy / Osmotic lens swelling\n3. Hyperosmolar Hyperglycemic State (early)",
        "draft",
        None,
        json.dumps({}),
        t_25m,
        t_25m
    ))

    # 4. Case 3: Amit Patel (Moderate / Routine Queue)
    case3_id = "case-ap-003"
    cursor.execute('''
    INSERT INTO cases (id, patient_id, patient_name, patient_age, patient_gender, language, chief_complaint, status, priority, priority_score, priority_reason, consent_given, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case3_id,
        None,
        "Amit Patel",
        32,
        "Male",
        "gu",
        "पेट में दर्द और हल्का बुखार (Abdominal cramps and low-grade fever for 2 days)",
        "submitted",
        "MEDIUM",
        42,
        "Acute crampy abdominal pain with low-grade fever (99.8 F); no peritoneal signs",
        1,
        t_40m,
        t_40m
    ))

    # 5. Case 4: Meera Sharma (Routine Checkup)
    case4_id = "case-ms-004"
    cursor.execute('''
    INSERT INTO cases (id, patient_id, patient_name, patient_age, patient_gender, language, chief_complaint, status, priority, priority_score, priority_reason, consent_given, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case4_id,
        None,
        "Meera Sharma",
        28,
        "Female",
        "en",
        "Annual health checkup and routine vitamin D / iron deficiency follow-up",
        "submitted",
        "ROUTINE",
        18,
        "Asymptomatic baseline routine health screening",
        1,
        t_1h,
        t_1h
    ))

    conn.commit()
    conn.close()
    print("Database seeded with realistic multi-patient clinical queue successfully!")

if __name__ == "__main__":
    seed_database()
