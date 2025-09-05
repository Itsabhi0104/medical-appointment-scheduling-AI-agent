import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration management"""
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    CALENDLY_PAT = os.getenv("CALENDLY_PAT")
    
    # Email Configuration
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    
    # Database
    DB_PATH = "data/appointments.db"
    
    # Doctors Configuration
    DOCTORS = ["Dr Asha Rao", "Dr Meera Iyer", "Dr Vikram Gupta"]
    
    # Business Rules
    NEW_PATIENT_DURATION = 60  # minutes
    RETURNING_PATIENT_DURATION = 30  # minutes
    
    # Working Hours (24-hour format)
    CLINIC_START_HOUR = 9
    CLINIC_END_HOUR = 17
    
    # File Paths
    FORMS_PATH = "forms"
    EXPORTS_PATH = "exports"
    LOGS_PATH = "logs"
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate required configuration"""
        required_vars = [
            cls.GEMINI_API_KEY,
            cls.CALENDLY_PAT,
            cls.EMAIL_USER,
            cls.EMAIL_PASSWORD
        ]
        
        missing = [var for var in required_vars if not var]
        if missing:
            print(f"Missing required environment variables: {len(missing)} items")
            return False
        
        return True

# Global config instance
config = Config()