from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

class Appointment(BaseModel):
    appointment_id: str
    patient_id: str
    doctor: str
    start_time: str  # ISO format
    end_time: str    # ISO format
    duration_minutes: int
    status: str = "scheduled"  # scheduled, confirmed, cancelled, completed
    reason: Optional[str] = None
    form_sent: bool = False
    calendly_url: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    @validator('start_time', 'end_time')
    def validate_datetime(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('DateTime must be in ISO format')

    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["scheduled", "confirmed", "cancelled", "completed"]
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of: {valid_statuses}')
        return v

    def to_dict(self):
        return {
            "appointment_id": self.appointment_id,
            "patient_id": self.patient_id,
            "doctor": self.doctor,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "reason": self.reason or "",
            "form_sent": int(self.form_sent),
            "calendly_url": self.calendly_url or "",
            "created_at": self.created_at,
            "updated_at": self.updated_at or ""
        }