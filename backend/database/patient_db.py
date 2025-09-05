import sqlite3
import os
from typing import Optional, List, Dict
from ..models.patient import Patient
import logging

logger = logging.getLogger(__name__)

class PatientDB:
    def __init__(self, db_path: str = "data/appointments.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize patients table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                dob TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                insurance_company TEXT,
                member_id TEXT,
                is_returning INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_appointment TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def create_patient(self, patient: Patient) -> bool:
        """Create a new patient"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO patients 
                (patient_id, first_name, last_name, dob, phone, email, 
                 insurance_company, member_id, is_returning, created_at, last_appointment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient.patient_id, patient.first_name, patient.last_name,
                patient.dob, patient.phone, patient.email,
                patient.insurance_company, patient.member_id,
                int(patient.is_returning), patient.created_at, patient.last_appointment
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error creating patient: {e}")
            return False

    def find_patient_by_details(self, first_name: str, last_name: str, dob: str) -> Optional[Patient]:
        """Find patient by name and DOB"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM patients 
                WHERE LOWER(first_name) = LOWER(?) 
                AND LOWER(last_name) = LOWER(?) 
                AND dob = ?
            """, (first_name, last_name, dob))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return Patient(
                    patient_id=row['patient_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    dob=row['dob'],
                    phone=row['phone'],
                    email=row['email'],
                    insurance_company=row['insurance_company'],
                    member_id=row['member_id'],
                    is_returning=bool(row['is_returning']),
                    created_at=row['created_at'],
                    last_appointment=row['last_appointment']
                )
            return None
            
        except Exception as e:
            logger.error(f"Error finding patient: {e}")
            return None

    def get_patient_by_id(self, patient_id: str) -> Optional[Patient]:
        """Get patient by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return Patient(
                    patient_id=row['patient_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    dob=row['dob'],
                    phone=row['phone'],
                    email=row['email'],
                    insurance_company=row['insurance_company'],
                    member_id=row['member_id'],
                    is_returning=bool(row['is_returning']),
                    created_at=row['created_at'],
                    last_appointment=row['last_appointment']
                )
            return None
            
        except Exception as e:
            logger.error(f"Error getting patient: {e}")
            return None

    def update_patient(self, patient_id: str, updates: Dict) -> bool:
        """Update patient information"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field in ['first_name', 'last_name', 'dob', 'phone', 'email', 
                           'insurance_company', 'member_id', 'is_returning', 'last_appointment']:
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
            
            if set_clauses:
                values.append(patient_id)
                query = f"UPDATE patients SET {', '.join(set_clauses)} WHERE patient_id = ?"
                cursor.execute(query, values)
                conn.commit()
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating patient: {e}")
            return False

    def get_all_patients(self) -> List[Patient]:
        """Get all patients"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()
            
            patients = []
            for row in rows:
                patients.append(Patient(
                    patient_id=row['patient_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    dob=row['dob'],
                    phone=row['phone'],
                    email=row['email'],
                    insurance_company=row['insurance_company'],
                    member_id=row['member_id'],
                    is_returning=bool(row['is_returning']),
                    created_at=row['created_at'],
                    last_appointment=row['last_appointment']
                ))
            
            return patients
            
        except Exception as e:
            logger.error(f"Error getting all patients: {e}")
            return []

# Global instance
patient_db = PatientDB()