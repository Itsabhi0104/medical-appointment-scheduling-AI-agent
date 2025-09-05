# scripts/ensure_appointments_table.py
import sqlite3, os
from datetime import datetime, timezone

DB = os.path.join("data", "appointments.db")
os.makedirs("data", exist_ok=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY,
    patient_id TEXT,
    doctor_sheet TEXT,
    doctor_id TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_minutes INTEGER,
    status TEXT,
    created_at TEXT,
    updated_at TEXT,
    form_sent INTEGER DEFAULT 0,
    calendly_event_uri TEXT
);
"""

def ensure():
    conn = sqlite3.connect(DB, timeout=30)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)
    conn.commit()
    cur.execute("PRAGMA table_info(appointments)")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    print("appointments columns:", cols)
    return cols

if __name__ == "__main__":
    ensure()
