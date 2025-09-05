from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

class Patient(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    dob: str  # YYYY-MM-DD format
    phone: Optional[str] = None
    email: Optional[str] = None
    insurance_company: Optional[str] = None
    member_id: Optional[str] = None
    is_returning: bool = False
    created_at: str
    last_appointment: Optional[str] = None

    @validator('dob')
    def validate_dob(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('DOB must be in YYYY-MM-DD format')

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "dob": self.dob,
            "phone": self.phone or "",
            "email": self.email or "",
            "insurance_company": self.insurance_company or "",
            "member_id": self.member_id or "",
            "is_returning": self.is_returning,
            "created_at": self.created_at,
            "last_appointment": self.last_appointment or ""
        }