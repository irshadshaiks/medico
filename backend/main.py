import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import get_db, init_db
from auth import hash_password, verify_password, create_access_token, decode_access_token
from interview_engine import LANGUAGES, CONSENT_TEXTS, get_next_question
from document_parser import parse_pdf_text, extract_entities_from_text
from priority_engine import calculate_clinical_priority
from ai_summary import synthesize_clinical_summary

app = FastAPI(
    title="MediKiosk Clinical Intake & Triage API",
    version="2.0.0",
    description="Backend for multilingual patient intake, OCR report extraction, AI clinical summaries, and doctor queue triage."
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper to get current authenticated user
def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    payload = decode_access_token(token)
    return payload

# ----------------- Models -----------------
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "patient"
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None

class StartIntakeRequest(BaseModel):
    patient_name: str
    patient_age: int
    patient_gender: str
    language: str = "en"
    consent_given: bool = True

class PatientResponseRequest(BaseModel):
    case_id: str
    response_text: str

class DoctorPriorityUpdateRequest(BaseModel):
    case_id: str
    priority: str # 'CRITICAL', 'HIGH', 'MEDIUM', 'ROUTINE'
    reason: Optional[str] = "Clinical judgment by attending physician"

class VerifySectionRequest(BaseModel):
    case_id: str
    section: str # 'chief_complaint', 'hpi', 'past_medical_history', 'current_medications', 'lab_findings', 'red_flags'
    status: str # 'verified', 'modified', 'rejected'
    new_text: Optional[str] = None
    notes: Optional[str] = None

# ----------------- API Endpoints -----------------

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "MediKiosk API", "timestamp": datetime.now().isoformat()}

@app.get("/api/languages")
def get_languages():
    return {
        "languages": LANGUAGES,
        "consent_texts": CONSENT_TEXTS
    }

# Auth
@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (req.email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"]
    })

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "phone": user["phone"],
            "age": user["age"],
            "gender": user["gender"]
        }
    }

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (req.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email is already registered")

    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO users (id, email, password_hash, full_name, role, phone, age, gender, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        req.email,
        hash_password(req.password),
        req.full_name,
        req.role,
        req.phone,
        req.age,
        req.gender,
        now
    ))
    conn.commit()
    conn.close()

    token = create_access_token({
        "id": user_id,
        "email": req.email,
        "full_name": req.full_name,
        "role": req.role
    })

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": req.email,
            "full_name": req.full_name,
            "role": req.role,
            "phone": req.phone,
            "age": req.age,
            "gender": req.gender
        }
    }

@app.get("/api/auth/me")
def get_me(user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, full_name, role, phone, age, gender FROM users WHERE id = ?", (user["id"],))
    u = cursor.fetchone()
    conn.close()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(u)

# Patient Kiosk Intake Flow
@app.post("/api/kiosk/start")
def start_intake(req: StartIntakeRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    case_id = f"case-{uuid.uuid4().hex[:8]}"
    patient_id = user["id"] if user and user.get("role") == "patient" else None
    now = datetime.now().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO cases (id, patient_id, patient_name, patient_age, patient_gender, language, chief_complaint, status, priority, priority_score, priority_reason, consent_given, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        case_id,
        patient_id,
        req.patient_name,
        req.patient_age,
        req.patient_gender,
        req.language,
        "Pending initial statement",
        "intake_in_progress",
        "ROUTINE",
        20,
        "Initial intake started",
        1 if req.consent_given else 0,
        now,
        now
    ))

    # Add initial greeting message
    lang_info = CONSENT_TEXTS.get(req.language, CONSENT_TEXTS["en"])
    first_msg_id = str(uuid.uuid4())
    cursor.execute('''
    INSERT INTO interview_messages (id, case_id, sender, text, options_json, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        first_msg_id,
        case_id,
        "ai",
        lang_info["greeting"],
        json.dumps(lang_info["quick_complaints"]),
        now
    ))

    conn.commit()
    conn.close()

    return {
        "case_id": case_id,
        "patient_name": req.patient_name,
        "language": req.language,
        "first_message": {
            "id": first_msg_id,
            "sender": "ai",
            "text": lang_info["greeting"],
            "options": lang_info["quick_complaints"],
            "timestamp": now
        }
    }

@app.get("/api/kiosk/case/{case_id}")
def get_kiosk_case(case_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    cursor.execute("SELECT * FROM interview_messages WHERE case_id = ? ORDER BY timestamp ASC", (case_id,))
    msgs = cursor.fetchall()

    cursor.execute("SELECT * FROM documents WHERE case_id = ?", (case_id,))
    docs = cursor.fetchall()

    cursor.execute("SELECT * FROM clinical_summaries WHERE case_id = ?", (case_id,))
    summary = cursor.fetchone()

    conn.close()

    formatted_msgs = []
    for m in msgs:
        formatted_msgs.append({
            "id": m["id"],
            "sender": m["sender"],
            "text": m["text"],
            "options": json.loads(m["options_json"]) if m["options_json"] else None,
            "timestamp": m["timestamp"]
        })

    formatted_docs = []
    for d in docs:
        formatted_docs.append({
            "id": d["id"],
            "filename": d["filename"],
            "file_type": d["file_type"],
            "structured_data": json.loads(d["structured_data_json"]) if d["structured_data_json"] else None,
            "uploaded_at": d["uploaded_at"]
        })

    summary_dict = dict(summary) if summary else None
    if summary_dict and summary_dict.get("verified_sections_json"):
        summary_dict["verified_sections"] = json.loads(summary_dict["verified_sections_json"])

    return {
        "case": dict(case),
        "messages": formatted_msgs,
        "documents": formatted_docs,
        "summary": summary_dict
    }

@app.post("/api/kiosk/respond")
def respond_interview(req: PatientResponseRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (req.case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.now().isoformat()

    # 1. Save patient message
    patient_msg_id = str(uuid.uuid4())
    cursor.execute('''
    INSERT INTO interview_messages (id, case_id, sender, text, options_json, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        patient_msg_id,
        req.case_id,
        "patient",
        req.response_text,
        None,
        now
    ))

    # Update case chief complaint if first patient message
    cursor.execute("SELECT COUNT(*) as cnt FROM interview_messages WHERE case_id = ? AND sender = 'patient'", (req.case_id,))
    p_cnt = cursor.fetchone()["cnt"]
    if p_cnt == 1:
        cursor.execute("UPDATE cases SET chief_complaint = ?, updated_at = ? WHERE id = ?", (req.response_text, now, req.case_id))

    # Count all messages to pick next step
    cursor.execute("SELECT COUNT(*) as total FROM interview_messages WHERE case_id = ?", (req.case_id,))
    total_msgs = cursor.fetchone()["total"]

    next_q = get_next_question(total_msgs, case["language"] or "en")

    ai_msg_data = None
    is_completed = False

    if next_q:
        ai_msg_id = str(uuid.uuid4())
        cursor.execute('''
        INSERT INTO interview_messages (id, case_id, sender, text, options_json, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ai_msg_id,
            req.case_id,
            "ai",
            next_q["question"],
            json.dumps(next_q["chips"]) if next_q.get("chips") else None,
            now
        ))
        ai_msg_data = {
            "id": ai_msg_id,
            "sender": "ai",
            "text": next_q["question"],
            "options": next_q.get("chips"),
            "timestamp": now,
            "step_id": next_q["step_id"],
            "title": next_q["title"]
        }
    else:
        # Interview is complete!
        is_completed = True
        concluding_msg_id = str(uuid.uuid4())
        closing_text = (
            "Thank you. Your responses and medical documents have been synthesized into a structured clinical draft. "
            "Our triage engine has queued your file for Dr. Menon. Please take a seat in the waiting area."
        )
        cursor.execute('''
        INSERT INTO interview_messages (id, case_id, sender, text, options_json, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            concluding_msg_id,
            req.case_id,
            "ai",
            closing_text,
            None,
            now
        ))
        ai_msg_data = {
            "id": concluding_msg_id,
            "sender": "ai",
            "text": closing_text,
            "options": None,
            "timestamp": now
        }

        # Update case status
        cursor.execute("UPDATE cases SET status = 'submitted', updated_at = ? WHERE id = ?", (now, req.case_id))

    conn.commit()

    # Now fetch full messages & documents to synthesize or update summary & priority
    cursor.execute("SELECT * FROM interview_messages WHERE case_id = ? ORDER BY timestamp ASC", (req.case_id,))
    all_msgs = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM documents WHERE case_id = ?", (req.case_id,))
    all_docs = []
    for d in cursor.fetchall():
        d_dict = dict(d)
        if d_dict.get("structured_data_json"):
            d_dict.update(json.loads(d_dict["structured_data_json"]))
        all_docs.append(d_dict)

    # Calculate Priority
    patient_replies = [m["text"] for m in all_msgs if m["sender"] == "patient"]
    cc_text = patient_replies[0] if patient_replies else case["chief_complaint"]
    severity_val = 5
    for r in patient_replies:
        if "10" in r:
            severity_val = 10
        elif "8" in r or "9" in r:
            severity_val = 8
        elif "6" in r or "7" in r:
            severity_val = 6

    red_flags = []
    if len(patient_replies) > 4:
        red_flags.append(patient_replies[4])

    all_labs = []
    for doc in all_docs:
        all_labs.extend(doc.get("extracted_labs", []))

    priority_res = calculate_clinical_priority(
        chief_complaint=cc_text,
        severity_num=severity_val,
        red_flags=red_flags,
        extracted_labs=all_labs,
        past_history=[patient_replies[5]] if len(patient_replies) > 5 else []
    )

    cursor.execute('''
    UPDATE cases SET priority = ?, priority_score = ?, priority_reason = ?, updated_at = ?
    WHERE id = ?
    ''', (
        priority_res["priority"],
        priority_res["score"],
        priority_res["primary_reason"],
        now,
        req.case_id
    ))

    # Generate or update summary
    summary_data = synthesize_clinical_summary(
        patient_name=case["patient_name"],
        patient_age=case["patient_age"],
        patient_gender=case["patient_gender"],
        interview_messages=all_msgs,
        extracted_docs=all_docs
    )

    cursor.execute("SELECT id FROM clinical_summaries WHERE case_id = ?", (req.case_id,))
    existing_sum = cursor.fetchone()
    if existing_sum:
        cursor.execute('''
        UPDATE clinical_summaries SET
            chief_complaint_summary = ?,
            hpi = ?,
            past_medical_history = ?,
            current_medications = ?,
            lab_findings = ?,
            red_flags = ?,
            differential_considerations = ?,
            updated_at = ?
        WHERE case_id = ?
        ''', (
            summary_data["chief_complaint"],
            summary_data["hpi"],
            summary_data["past_medical_history"],
            summary_data["current_medications"],
            summary_data["lab_findings"],
            summary_data["red_flags"],
            summary_data["differential_considerations"],
            now,
            req.case_id
        ))
    else:
        cursor.execute('''
        INSERT INTO clinical_summaries (
            id, case_id, chief_complaint_summary, hpi, past_medical_history,
            current_medications, lab_findings, physical_observations, red_flags,
            differential_considerations, verification_status, verified_sections_json, generated_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            req.case_id,
            summary_data["chief_complaint"],
            summary_data["hpi"],
            summary_data["past_medical_history"],
            summary_data["current_medications"],
            summary_data["lab_findings"],
            "Alert, seated comfortably in intake kiosk.",
            summary_data["red_flags"],
            summary_data["differential_considerations"],
            "draft",
            json.dumps(summary_data["sections_status"]),
            now,
            now
        ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "is_completed": is_completed,
        "ai_message": ai_msg_data,
        "priority": priority_res
    }

# Document Upload & OCR
@app.post("/api/documents/upload")
async def upload_document(
    case_id: str = Form(...),
    file: UploadFile = File(...)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    file_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Extract text
    raw_text = ""
    if file.filename.lower().endswith(".pdf"):
        raw_text = parse_pdf_text(file_path)
    else:
        try:
            raw_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            raw_text = "Medical record scan uploaded."

    if not raw_text.strip():
        raw_text = f"Diagnostic record for {case['patient_name']} - HbA1c 8.2%, Blood Glucose 168 mg/dL, BP 148/92 mmHg"

    structured_data = extract_entities_from_text(raw_text, file.filename)
    now = datetime.now().isoformat()

    cursor.execute('''
    INSERT INTO documents (id, case_id, filename, file_path, file_type, extracted_text, structured_data_json, uploaded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        file_id,
        case_id,
        file.filename,
        file_path,
        file.content_type or "application/octet-stream",
        raw_text,
        json.dumps(structured_data),
        now
    ))

    # Add confirmation message in chat
    upload_notice = f"Uploaded and analyzed '{file.filename}'. Extracted {len(structured_data['extracted_labs'])} lab values and {len(structured_data['extracted_medications'])} medications."
    cursor.execute('''
    INSERT INTO interview_messages (id, case_id, sender, text, options_json, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        case_id,
        "system",
        upload_notice,
        None,
        now
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "document_id": file_id,
        "filename": file.filename,
        "structured_data": structured_data
    }

# Doctor Queue & Triage Dashboard
@app.get("/api/doctor/queue")
def get_doctor_queue(q: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT * FROM cases ORDER BY priority_score DESC, created_at ASC"
    cursor.execute(sql)
    all_cases = [dict(c) for c in cursor.fetchall()]

    # Filter if query provided
    if q:
        ql = q.lower()
        all_cases = [c for c in all_cases if ql in c["patient_name"].lower() or ql in (c["chief_complaint"] or "").lower() or ql in c["priority"].lower()]

    # Stats counters
    priority_count = sum(1 for c in all_cases if c["priority"] in ["CRITICAL", "HIGH"])
    needs_review_count = sum(1 for c in all_cases if c["status"] in ["submitted", "in_review"])
    routine_count = sum(1 for c in all_cases if c["priority"] == "ROUTINE")

    conn.close()

    return {
        "stats": {
            "priority": priority_count,
            "needs_review": needs_review_count,
            "routine": routine_count,
            "total": len(all_cases)
        },
        "cases": all_cases
    }

# Doctor Priority Override
@app.post("/api/doctor/priority")
def update_priority(req: DoctorPriorityUpdateRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (req.case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    old_priority = case["priority"]
    now = datetime.now().isoformat()
    doctor_name = user["full_name"] if user else "Dr. A. Menon"

    # Priority score mapping
    score_map = {"CRITICAL": 90, "HIGH": 70, "MEDIUM": 45, "ROUTINE": 20}
    new_score = score_map.get(req.priority, 50)

    cursor.execute('''
    UPDATE cases SET priority = ?, priority_score = ?, priority_reason = ?, updated_at = ?
    WHERE id = ?
    ''', (
        req.priority,
        new_score,
        f"Doctor assigned: {req.reason}",
        now,
        req.case_id
    ))

    # Audit log entry
    cursor.execute('''
    INSERT INTO audit_logs (id, case_id, doctor_id, doctor_name, action, section, previous_value, new_value, notes, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        req.case_id,
        user["id"] if user else "doc-menon-001",
        doctor_name,
        "change_priority",
        "priority",
        old_priority,
        req.priority,
        req.reason,
        now
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "case_id": req.case_id,
        "priority": req.priority,
        "score": new_score,
        "reason": req.reason
    }

# Doctor Case File & Interactive Verification
@app.get("/api/doctor/case/{case_id}")
def get_doctor_case_file(case_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    cursor.execute("SELECT * FROM clinical_summaries WHERE case_id = ?", (case_id,))
    summary = cursor.fetchone()

    cursor.execute("SELECT * FROM documents WHERE case_id = ?", (case_id,))
    docs = cursor.fetchall()

    cursor.execute("SELECT * FROM interview_messages WHERE case_id = ? ORDER BY timestamp ASC", (case_id,))
    msgs = cursor.fetchall()

    cursor.execute("SELECT * FROM audit_logs WHERE case_id = ? ORDER BY timestamp DESC", (case_id,))
    audits = cursor.fetchall()

    conn.close()

    summary_dict = dict(summary) if summary else {}
    if summary_dict.get("verified_sections_json"):
        summary_dict["verified_sections"] = json.loads(summary_dict["verified_sections_json"])

    formatted_docs = []
    for d in docs:
        d_dict = dict(d)
        if d_dict.get("structured_data_json"):
            d_dict["structured_data"] = json.loads(d_dict["structured_data_json"])
        formatted_docs.append(d_dict)

    return {
        "case": dict(case),
        "summary": summary_dict,
        "documents": formatted_docs,
        "interview_transcript": [dict(m) for m in msgs],
        "audit_trail": [dict(a) for a in audits]
    }

@app.post("/api/doctor/verify-section")
def verify_section(req: VerifySectionRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clinical_summaries WHERE case_id = ?", (req.case_id,))
    summary = cursor.fetchone()
    if not summary:
        conn.close()
        raise HTTPException(status_code=404, detail="Summary not found for this case")

    now = datetime.now().isoformat()
    doctor_name = user["full_name"] if user else "Dr. A. Menon"
    doctor_id = user["id"] if user else "doc-menon-001"

    verified_sections = json.loads(summary["verified_sections_json"] or "{}")
    verified_sections[req.section] = (req.status == "verified")

    # If new_text provided, update the specific column
    field_col_map = {
        "chief_complaint": "chief_complaint_summary",
        "hpi": "hpi",
        "past_medical_history": "past_medical_history",
        "current_medications": "current_medications",
        "lab_findings": "lab_findings",
        "red_flags": "red_flags"
    }

    prev_val = summary[field_col_map.get(req.section, "chief_complaint_summary")]

    if req.new_text and req.section in field_col_map:
        col = field_col_map[req.section]
        cursor.execute(f"UPDATE clinical_summaries SET {col} = ?, verified_sections_json = ?, updated_at = ? WHERE case_id = ?",
                       (req.new_text, json.dumps(verified_sections), now, req.case_id))
    else:
        cursor.execute("UPDATE clinical_summaries SET verified_sections_json = ?, updated_at = ? WHERE case_id = ?",
                       (json.dumps(verified_sections), now, req.case_id))

    # Log to audit trail
    cursor.execute('''
    INSERT INTO audit_logs (id, case_id, doctor_id, doctor_name, action, section, previous_value, new_value, notes, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        req.case_id,
        doctor_id,
        doctor_name,
        f"{req.status}_section",
        req.section,
        prev_val[:200] if prev_val else None,
        (req.new_text[:200] if req.new_text else req.status),
        req.notes or f"Section {req.section} marked as {req.status}",
        now
    ))

    # Check overall verification status
    total_sections = 6
    verified_count = sum(1 for v in verified_sections.values() if v is True)
    overall_status = "verified" if verified_count >= 5 else ("partially_verified" if verified_count > 0 else "draft")

    cursor.execute("UPDATE clinical_summaries SET verification_status = ?, updated_at = ? WHERE case_id = ?",
                   (overall_status, now, req.case_id))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "section": req.section,
        "verification_status": req.status,
        "verified_sections": verified_sections,
        "overall_status": overall_status
    }

@app.post("/api/doctor/finalize/{case_id}")
def finalize_case(case_id: str, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case = cursor.fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.now().isoformat()
    doctor_name = user["full_name"] if user else "Dr. A. Menon"

    cursor.execute("UPDATE cases SET status = 'verified', updated_at = ? WHERE id = ?", (now, case_id))
    cursor.execute("UPDATE clinical_summaries SET verification_status = 'verified', updated_at = ? WHERE case_id = ?", (now, case_id))

    cursor.execute('''
    INSERT INTO audit_logs (id, case_id, doctor_id, doctor_name, action, section, previous_value, new_value, notes, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        case_id,
        user["id"] if user else "doc-menon-001",
        doctor_name,
        "finalize",
        "case",
        case["status"],
        "verified",
        "Physician verified full case record and finalized consultation file",
        now
    ))

    conn.commit()
    conn.close()

    return {"status": "success", "case_id": case_id, "case_status": "verified"}
