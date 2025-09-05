import sqlite3
import os
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from ..models.appointment import Appointment
import logging

logger = logging.getLogger(__name__)

class AppointmentDB:
    def __init__(self, db_path: str = "data/appointments.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize appointments table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                doctor TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                status TEXT DEFAULT 'scheduled',
                reason TEXT,
                form_sent INTEGER DEFAULT 0,
                calendly_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
            )
        """)
        
        conn.commit()
        conn.close()

    def create_appointment(self, appointment: Appointment) -> bool:
        """Create a new appointment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO appointments 
                (appointment_id, patient_id, doctor, start_time, end_time, 
                 duration_minutes, status, reason, form_sent, calendly_url, 
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                appointment.appointment_id, appointment.patient_id, appointment.doctor,
                appointment.start_time, appointment.end_time, appointment.duration_minutes,
                appointment.status, appointment.reason, int(appointment.form_sent),
                appointment.calendly_url, appointment.created_at, appointment.updated_at
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return False

    def get_appointment_by_id(self, appointment_id: str) -> Optional[Appointment]:
        """Get appointment by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return Appointment(
                    appointment_id=row['appointment_id'],
                    patient_id=row['patient_id'],
                    doctor=row['doctor'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    duration_minutes=row['duration_minutes'],
                    status=row['status'],
                    reason=row['reason'],
                    form_sent=bool(row['form_sent']),
                    calendly_url=row['calendly_url'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None
            
        except Exception as e:
            logger.error(f"Error getting appointment: {e}")
            return None

    def update_appointment(self, appointment_id: str, updates: Dict) -> bool:
        """Update appointment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field in ['status', 'reason', 'form_sent', 'calendly_url', 'updated_at']:
                    set_clauses.append(f"{field} = ?")
                    if field == 'form_sent':
                        values.append(int(value))
                    else:
                        values.append(value)
            
            # Always update timestamp
            if 'updated_at' not in updates:
                set_clauses.append("updated_at = ?")
                values.append(datetime.now().isoformat())
            
            values.append(appointment_id)
            query = f"UPDATE appointments SET {', '.join(set_clauses)} WHERE appointment_id = ?"
            cursor.execute(query, values)
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return False

    def get_appointments_by_patient(self, patient_id: str) -> List[Appointment]:
        """Get appointments for a patient"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM appointments 
                WHERE patient_id = ? 
                ORDER BY start_time DESC
            """, (patient_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            appointments = []
            for row in rows:
                appointments.append(Appointment(
                    appointment_id=row['appointment_id'],
                    patient_id=row['patient_id'],
                    doctor=row['doctor'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    duration_minutes=row['duration_minutes'],
                    status=row['status'],
                    reason=row['reason'],
                    form_sent=bool(row['form_sent']),
                    calendly_url=row['calendly_url'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting patient appointments: {e}")
            return []

    def get_appointments_by_doctor_and_date(self, doctor: str, date_str: str) -> List[Appointment]:
        """Get appointments for doctor on specific date"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Date range for the day
            start_date = f"{date_str}T00:00:00"
            end_date = f"{date_str}T23:59:59"
            
            cursor.execute("""
                SELECT * FROM appointments 
                WHERE doctor = ? 
                AND start_time >= ? 
                AND start_time <= ?
                AND status != 'cancelled'
                ORDER BY start_time
            """, (doctor, start_date, end_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            appointments = []
            for row in rows:
                appointments.append(Appointment(
                    appointment_id=row['appointment_id'],
                    patient_id=row['patient_id'],
                    doctor=row['doctor'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    duration_minutes=row['duration_minutes'],
                    status=row['status'],
                    reason=row['reason'],
                    form_sent=bool(row['form_sent']),
                    calendly_url=row['calendly_url'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting doctor appointments: {e}")
            return []

    def get_all_appointments(self, days_ahead: int = 30) -> List[Appointment]:
        """Get all appointments within specified days"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            end_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
            
            cursor.execute("""
                SELECT * FROM appointments 
                WHERE start_time <= ?
                ORDER BY start_time DESC
            """, (end_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            appointments = []
            for row in rows:
                appointments.append(Appointment(
                    appointment_id=row['appointment_id'],
                    patient_id=row['patient_id'],
                    doctor=row['doctor'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    duration_minutes=row['duration_minutes'],
                    status=row['status'],
                    reason=row['reason'],
                    form_sent=bool(row['form_sent']),
                    calendly_url=row['calendly_url'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting all appointments: {e}")
            return []

# Global instance
appointment_db = AppointmentDB()