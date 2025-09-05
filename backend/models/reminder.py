from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Reminder(BaseModel):
    reminder_id: str
    appointment_id: str
    reminder_type: str  # first, second, third
    scheduled_time: str  # ISO format
    status: str = "pending"  # pending, sent, failed
    email_sent: bool = False
    sms_sent: bool = False
    response_received: bool = False
    patient_response: Optional[str] = None
    created_at: str
    sent_at: Optional[str] = None

    def to_dict(self):
        return {
            "reminder_id": self.reminder_id,
            "appointment_id": self.appointment_id,
            "reminder_type": self.reminder_type,
            "scheduled_time": self.scheduled_time,
            "status": self.status,
            "email_sent": int(self.email_sent),
            "sms_sent": int(self.sms_sent),
            "response_received": int(self.response_received),
            "patient_response": self.patient_response or "",
            "created_at": self.created_at,
            "sent_at": self.sent_at or ""
        }