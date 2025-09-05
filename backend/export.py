# backend/export.py
import os
import sqlite3
import pandas as pd
import datetime

DB_PATH = "data/appointments.db"
EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)


def export_bookings():
    """Export all confirmed appointments to Excel for admins."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Ensure appointments table exists
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id TEXT PRIMARY KEY,
            patient_id TEXT,
            doctor_sheet TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_minutes INTEGER,
            status TEXT,
            created_at TEXT,
            form_sent INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()

    # Load all appointments
    df = pd.read_sql_query("SELECT * FROM appointments", conn)

    # Map form_sent to Y/N
    if "form_sent" in df.columns:
        df["form_sent"] = df["form_sent"].apply(
            lambda x: "Y" if str(x).strip() in ("1", "True", "true") else "N"
        )
    else:
        df["form_sent"] = "N"

    # Standardize columns for export
    export_df = df[
        [
            "appointment_id",
            "patient_id",
            "doctor_sheet",
            "start_time",
            "duration_minutes",
            "status",
            "form_sent",
        ]
    ].copy()

    # Rename for clarity
    export_df.rename(
        columns={
            "doctor_sheet": "doctor",
            "duration_minutes": "duration",
        },
        inplace=True,
    )

    # Create export filename
    today = datetime.date.today().strftime("%Y%m%d")
    out_path = os.path.join(EXPORT_DIR, f"bookings_{today}.xlsx")

    export_df.to_excel(out_path, index=False)
    conn.close()

    return out_path


def mark_form_sent(appointment_id: str):
    """Mark a specific appointment as form_sent = 1."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET form_sent = 1 WHERE appointment_id = ?", (appointment_id,)
    )
    conn.commit()
    conn.close()
