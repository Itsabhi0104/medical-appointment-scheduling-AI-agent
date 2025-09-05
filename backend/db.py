from __future__ import annotations
import os
import pandas as pd
import sqlite3
from typing import Optional, Dict

DATA_DIR = os.path.join("data")
PATIENTS_CSV = os.path.join(DATA_DIR, "patients.csv")
APPOINTMENTS_DB = os.path.join(DATA_DIR, "appointments.db")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def _ensure_patients_csv():
    """If patients.csv not present, create an empty template with header."""
    if not os.path.exists(PATIENTS_CSV):
        df = pd.DataFrame(
            columns=[
                "patient_id",
                "first_name",
                "last_name",
                "dob",
                "phone",
                "email",
                "insurance_company",
                "member_id",
                "is_returning",
            ]
        )
        df.to_csv(PATIENTS_CSV, index=False)


def list_patients():
    """Return list of patient dicts from patients.csv"""
    _ensure_patients_csv()
    df = pd.read_csv(PATIENTS_CSV, dtype=str).fillna("")
    return df.to_dict(orient="records")


def find_patient_by_name_dob(first_name: str, last_name: str, dob: str) -> Optional[Dict]:
    """
    Find patient by exact first/last/dob match.
    DOB expected YYYY-MM-DD (string). Matching is case-insensitive for names.
    Returns row dict or None.
    """
    _ensure_patients_csv()
    df = pd.read_csv(PATIENTS_CSV, dtype=str).fillna("")
    # normalize
    fn = str(first_name or "").strip().lower()
    ln = str(last_name or "").strip().lower()
    dob_s = str(dob or "").strip()
    matches = df[
        (df["first_name"].str.strip().str.lower() == fn)
        & (df["last_name"].str.strip().str.lower() == ln)
        & (df["dob"].str.strip() == dob_s)
    ]
    if not matches.empty:
        return matches.iloc[0].to_dict()
    return None


def create_patient(p: Dict) -> Dict:
    """
    Create a new patient and append to patients.csv.
    p should contain keys: first_name, last_name, dob, phone, email, insurance_company, member_id, is_returning (optional)
    Returns the created patient row (including generated patient_id)
    """
    _ensure_patients_csv()
    df = pd.read_csv(PATIENTS_CSV, dtype=str).fillna("")
    # generate next patient id Pxxxx
    if "patient_id" in df.columns and not df.empty:
        try:
            maxnum = df["patient_id"].str.extract(r"P(\d+)").astype(float).max().max()
            next_num = int(maxnum or 0) + 1
        except Exception:
            next_num = len(df) + 1
    else:
        next_num = 1
    patient_id = f"P{next_num:04d}"
    row = {
        "patient_id": patient_id,
        "first_name": p.get("first_name", ""),
        "last_name": p.get("last_name", ""),
        "dob": p.get("dob", ""),
        "phone": p.get("phone", ""),
        "email": p.get("email", ""),
        "insurance_company": p.get("insurance_company", ""),
        "member_id": p.get("member_id", ""),
        "is_returning": bool(p.get("is_returning", False)),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(PATIENTS_CSV, index=False)
    return row


def get_patient_by_id(patient_id: str) -> Optional[Dict]:
    """Return patient row dict by patient_id, or None if not found."""
    _ensure_patients_csv()
    df = pd.read_csv(PATIENTS_CSV, dtype=str).fillna("")
    sel = df[df["patient_id"] == patient_id]
    if sel.empty:
        return None
    r = sel.iloc[0].to_dict()
    # ensure first_name/last_name present
    return {"first_name": r.get("first_name", ""), "last_name": r.get("last_name", ""), **r}


def get_db_connection():
    """
    Return a sqlite3.Connection to the appointments DB.
    The callers should set row_factory if they need dict-like rows.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(APPOINTMENTS_DB, timeout=30)
    return conn
