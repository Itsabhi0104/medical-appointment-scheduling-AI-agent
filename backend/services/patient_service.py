"""
Patient service with proper new/returning patient detection
"""
import os
import pandas as pd
import sqlite3
from typing import Optional, Dict, List
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class PatientService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.patients_csv = os.path.join(data_dir, "patients.csv")
        self.appointments_db = os.path.join(data_dir, "appointments.db")
        os.makedirs(data_dir, exist_ok=True)
        self._ensure_patients_csv()

    def _ensure_patients_csv(self):
        """Create patients.csv if it doesn't exist"""
        if not os.path.exists(self.patients_csv):
            df = pd.DataFrame(columns=[
                "patient_id", "first_name", "last_name", "dob", 
                "phone", "email", "insurance_company", "member_id", 
                "is_returning", "created_at", "last_appointment"
            ])
            df.to_csv(self.patients_csv, index=False)

    def find_patient(self, first_name: str, last_name: str, dob: str) -> Optional[Dict]:
        """Find patient by name and DOB"""
        try:
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            
            # Normalize inputs
            first_norm = str(first_name).strip().lower()
            last_norm = str(last_name).strip().lower()
            dob_norm = str(dob).strip()
            
            # Find matches
            matches = df[
                (df["first_name"].str.strip().str.lower() == first_norm) &
                (df["last_name"].str.strip().str.lower() == last_norm) &
                (df["dob"].str.strip() == dob_norm)
            ]
            
            if not matches.empty:
                patient = matches.iloc[0].to_dict()
                # Update last access
                self._update_last_access(patient["patient_id"])
                return patient
            
            return None
        
        except Exception as e:
            logger.error(f"Error finding patient: {e}")
            return None

    def create_patient(self, patient_data: Dict) -> Dict:
        """Create a new patient record"""
        try:
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            
            # Generate patient ID
            if not df.empty and "patient_id" in df.columns:
                existing_ids = df["patient_id"].str.extract(r'P(\d+)', expand=False).astype(float)
                next_id = int(existing_ids.max() or 0) + 1
            else:
                next_id = 1
            
            patient_id = f"P{next_id:04d}"
            
            # Check if patient is returning (has previous appointments)
            is_returning = self._check_returning_status(
                patient_data.get("first_name", ""),
                patient_data.get("last_name", ""),
                patient_data.get("phone", ""),
                patient_data.get("email", "")
            )
            
            # Create patient record
            new_patient = {
                "patient_id": patient_id,
                "first_name": patient_data.get("first_name", ""),
                "last_name": patient_data.get("last_name", ""),
                "dob": patient_data.get("dob", ""),
                "phone": patient_data.get("phone", ""),
                "email": patient_data.get("email", ""),
                "insurance_company": patient_data.get("insurance", ""),
                "member_id": patient_data.get("member_id", ""),
                "is_returning": is_returning,
                "created_at": datetime.now().isoformat(),
                "last_appointment": ""
            }
            
            # Add to CSV
            df = pd.concat([df, pd.DataFrame([new_patient])], ignore_index=True)
            df.to_csv(self.patients_csv, index=False)
            
            logger.info(f"Created patient {patient_id}: {new_patient['first_name']} {new_patient['last_name']}")
            return new_patient
        
        except Exception as e:
            logger.error(f"Error creating patient: {e}")
            raise

    def _check_returning_status(self, first_name: str, last_name: str, phone: str, email: str) -> bool:
        """Check if patient is returning based on similar records or appointments"""
        try:
            # Check existing patients with similar info
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            
            # Check for similar names
            similar_name = df[
                (df["first_name"].str.lower() == first_name.lower()) &
                (df["last_name"].str.lower() == last_name.lower())
            ]
            
            if not similar_name.empty:
                return True
            
            # Check for same phone/email
            if phone:
                same_phone = df[df["phone"].str.contains(phone, na=False)]
                if not same_phone.empty:
                    return True
            
            if email:
                same_email = df[df["email"].str.contains(email, na=False, case=False)]
                if not same_email.empty:
                    return True
            
            # Check appointment history
            if os.path.exists(self.appointments_db):
                conn = sqlite3.connect(self.appointments_db)
                cursor = conn.cursor()
                
                # Look for appointments with similar patient info
                cursor.execute("""
                    SELECT COUNT(*) FROM appointments a
                    JOIN patients p ON a.patient_id = p.patient_id
                    WHERE LOWER(p.first_name) = ? AND LOWER(p.last_name) = ?
                """, (first_name.lower(), last_name.lower()))
                
                count = cursor.fetchone()[0]
                conn.close()
                
                return count > 0
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking returning status: {e}")
            return False

    def _update_last_access(self, patient_id: str):
        """Update last appointment access time"""
        try:
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            df.loc[df["patient_id"] == patient_id, "last_appointment"] = datetime.now().isoformat()
            df.to_csv(self.patients_csv, index=False)
        except Exception as e:
            logger.error(f"Error updating last access: {e}")

    def get_patient_appointment_duration(self, patient: Dict) -> int:
        """Get recommended appointment duration based on patient status"""
        if patient.get("is_returning") == "True" or patient.get("is_returning") is True:
            return 30  # Returning patient
        else:
            return 60  # New patient

    def list_all_patients(self) -> List[Dict]:
        """Get all patients"""
        try:
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            return df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Error listing patients: {e}")
            return []

    def update_patient(self, patient_id: str, updates: Dict) -> bool:
        """Update patient information"""
        try:
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            
            if patient_id not in df["patient_id"].values:
                return False
            
            for field, value in updates.items():
                if field in df.columns:
                    df.loc[df["patient_id"] == patient_id, field] = str(value)
            
            df.to_csv(self.patients_csv, index=False)
            return True
        
        except Exception as e:
            logger.error(f"Error updating patient: {e}")
            return False

    def get_patient_stats(self) -> Dict:
        """Get patient statistics"""
        try:
            df = pd.read_csv(self.patients_csv, dtype=str).fillna("")
            
            stats = {
                "total_patients": len(df),
                "new_patients": len(df[df["is_returning"] != "True"]),
                "returning_patients": len(df[df["is_returning"] == "True"]),
                "patients_with_insurance": len(df[df["insurance_company"] != ""]),
                "recent_registrations": len(df[
                    pd.to_datetime(df["created_at"], errors="coerce") > 
                    pd.Timestamp.now() - pd.Timedelta(days=30)
                ])
            }
            
            return stats
        
        except Exception as e:
            logger.error(f"Error getting patient stats: {e}")
            return {}

# Global instance
patient_service = PatientService()