import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "medikiosk.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'patient', -- 'patient' or 'doctor'
        phone TEXT,
        age INTEGER,
        gender TEXT,
        created_at TEXT NOT NULL
    )
    ''')

    # Cases
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY,
        patient_id TEXT,
        patient_name TEXT NOT NULL,
        patient_age INTEGER,
        patient_gender TEXT,
        language TEXT DEFAULT 'en',
        chief_complaint TEXT,
        status TEXT NOT NULL DEFAULT 'intake_in_progress', -- 'intake_in_progress', 'submitted', 'in_review', 'verified', 'completed'
        priority TEXT NOT NULL DEFAULT 'ROUTINE', -- 'CRITICAL', 'HIGH', 'MEDIUM', 'ROUTINE'
        priority_score INTEGER DEFAULT 20,
        priority_reason TEXT,
        consent_given INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES users(id)
    )
    ''')

    # Interview Messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interview_messages (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        sender TEXT NOT NULL, -- 'ai', 'patient', 'system'
        text TEXT NOT NULL,
        options_json TEXT, -- JSON array of suggestion chips
        timestamp TEXT NOT NULL,
        metadata_json TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(id)
    )
    ''')

    # Uploaded Documents
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        extracted_text TEXT,
        structured_data_json TEXT,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id)
    )
    ''')

    # Clinical Summaries
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clinical_summaries (
        id TEXT PRIMARY KEY,
        case_id TEXT UNIQUE NOT NULL,
        chief_complaint_summary TEXT,
        hpi TEXT,
        past_medical_history TEXT,
        current_medications TEXT,
        lab_findings TEXT,
        physical_observations TEXT,
        red_flags TEXT,
        differential_considerations TEXT,
        verification_status TEXT DEFAULT 'draft', -- 'draft', 'partially_verified', 'verified'
        doctor_notes TEXT,
        verified_sections_json TEXT, -- JSON object tracking verified sections
        generated_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id)
    )
    ''')

    # Audit Logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        doctor_id TEXT,
        doctor_name TEXT,
        action TEXT NOT NULL, -- 'verify_section', 'edit_section', 'reject_section', 'change_priority', 'finalize'
        section TEXT,
        previous_value TEXT,
        new_value TEXT,
        notes TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id)
    )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
