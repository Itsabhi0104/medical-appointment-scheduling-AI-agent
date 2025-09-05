import sqlite3
import os
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from ..models.reminder import Reminder
import logging

logger = logging.getLogger(__name__)

class ReminderDB:
    def __init__(self, db_path: str = "data/appointments.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize reminders table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id TEXT PRIMARY KEY,
                appointment_id TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                email_sent INTEGER DEFAULT 0,
                sms_sent INTEGER DEFAULT 0,
                response_received INTEGER DEFAULT 0,
                patient_response TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT,
                FOREIGN KEY (appointment_id) REFERENCES appointments (appointment_id)
            )
        """)
        
        conn.commit()
        conn.close()

    def create_reminder(self, reminder: Reminder) -> bool:
        """Create a new reminder"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO reminders 
                (reminder_id, appointment_id, reminder_type, scheduled_time, 
                 status, email_sent, sms_sent, response_received, patient_response,
                 created_at, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reminder.reminder_id, reminder.appointment_id, reminder.reminder_type,
                reminder.scheduled_time, reminder.status, int(reminder.email_sent),
                int(reminder.sms_sent), int(reminder.response_received),
                reminder.patient_response, reminder.created_at, reminder.sent_at
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return False

    def get_reminders_by_appointment(self, appointment_id: str) -> List[Reminder]:
        """Get all reminders for an appointment"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM reminders 
                WHERE appointment_id = ?
                ORDER BY scheduled_time
            """, (appointment_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            reminders = []
            for row in rows:
                reminders.append(Reminder(
                    reminder_id=row['reminder_id'],
                    appointment_id=row['appointment_id'],
                    reminder_type=row['reminder_type'],
                    scheduled_time=row['scheduled_time'],
                    status=row['status'],
                    email_sent=bool(row['email_sent']),
                    sms_sent=bool(row['sms_sent']),
                    response_received=bool(row['response_received']),
                    patient_response=row['patient_response'],
                    created_at=row['created_at'],
                    sent_at=row['sent_at']
                ))
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error getting reminders: {e}")
            return []

    def get_pending_reminders(self) -> List[Reminder]:
        """Get reminders that need to be sent"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute("""
                SELECT * FROM reminders 
                WHERE status = 'pending' 
                AND scheduled_time <= ?
                ORDER BY scheduled_time
            """, (now,))
            
            rows = cursor.fetchall()
            conn.close()
            
            reminders = []
            for row in rows:
                reminders.append(Reminder(
                    reminder_id=row['reminder_id'],
                    appointment_id=row['appointment_id'],
                    reminder_type=row['reminder_type'],
                    scheduled_time=row['scheduled_time'],
                    status=row['status'],
                    email_sent=bool(row['email_sent']),
                    sms_sent=bool(row['sms_sent']),
                    response_received=bool(row['response_received']),
                    patient_response=row['patient_response'],
                    created_at=row['created_at'],
                    sent_at=row['sent_at']
                ))
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error getting pending reminders: {e}")
            return []

    def update_reminder(self, reminder_id: str, updates: Dict) -> bool:
        """Update reminder status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field in ['status', 'email_sent', 'sms_sent', 'response_received', 
                           'patient_response', 'sent_at']:
                    set_clauses.append(f"{field} = ?")
                    if field in ['email_sent', 'sms_sent', 'response_received']:
                        values.append(int(value))
                    else:
                        values.append(value)
            
            if set_clauses:
                values.append(reminder_id)
                query = f"UPDATE reminders SET {', '.join(set_clauses)} WHERE reminder_id = ?"
                cursor.execute(query, values)
                conn.commit()
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating reminder: {e}")
            return False

    def record_patient_response(self, reminder_id: str, response: str) -> bool:
        """Record patient response to reminder"""
        return self.update_reminder(reminder_id, {
            'response_received': True,
            'patient_response': response,
            'status': 'completed'
        })

# Global instance
reminder_db = ReminderDB()