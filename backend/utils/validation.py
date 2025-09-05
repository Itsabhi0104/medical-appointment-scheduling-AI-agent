import re
from datetime import datetime
from typing import Optional, Dict, Any

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return False
    # Remove spaces, dashes, parentheses
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    # Check if it's a valid Indian phone number format
    pattern = r'^(\+91|91|0)?[6789]\d{9}$'
    return bool(re.match(pattern, clean_phone))

def validate_dob(dob: str) -> bool:
    """Validate date of birth"""
    try:
        birth_date = datetime.strptime(dob, '%Y-%m-%d')
        today = datetime.now()
        
        # Should be in the past
        if birth_date.date() >= today.date():
            return False
        
        # Reasonable age limits (0-120 years)
        age = (today - birth_date).days / 365.25
        return 0 <= age <= 120
    except:
        return False

def validate_appointment_date(date_str: str) -> bool:
    """Validate appointment date"""
    try:
        apt_date = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now()
        
        # Should be today or future
        if apt_date.date() < today.date():
            return False
        
        # Not too far in future (within 6 months)
        max_future = today.replace(month=today.month + 6 if today.month <= 6 else today.month - 6, year=today.year + (1 if today.month > 6 else 0))
        return apt_date <= max_future
    except:
        return False

def validate_doctor_name(doctor: str, valid_doctors: list) -> bool:
    """Validate doctor name against available doctors"""
    if not doctor or not valid_doctors:
        return False
    
    # Case-insensitive matching
    doctor_lower = doctor.lower()
    for valid_doc in valid_doctors:
        if valid_doc.lower() == doctor_lower:
            return True
    return False

def validate_insurance_info(insurance: str, member_id: str) -> bool:
    """Validate insurance information"""
    if not insurance:
        return False
    
    # Basic validation - insurance company name should be reasonable
    if len(insurance.strip()) < 2:
        return False
    
    # Member ID validation (if provided)
    if member_id:
        # Should be alphanumeric and reasonable length
        if not re.match(r'^[A-Za-z0-9]{3,20}$', member_id.strip()):
            return False
    
    return True

def sanitize_name(name: str) -> str:
    """Sanitize and format name"""
    if not name:
        return ""
    
    # Remove extra spaces and capitalize properly
    return ' '.join(word.capitalize() for word in name.strip().split())

def sanitize_phone(phone: str) -> str:
    """Sanitize phone number"""
    if not phone:
        return ""
    
    # Remove all non-digits except +
    clean = re.sub(r'[^\d\+]', '', phone)
    
    # Add +91 if missing for Indian numbers
    if len(clean) == 10 and clean.startswith(('6', '7', '8', '9')):
        clean = '+91' + clean
    
    return clean

def validate_patient_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate complete patient data"""
    errors = {}
    warnings = []
    
    # Required fields
    if not data.get('first_name'):
        errors['first_name'] = "First name is required"
    elif len(data['first_name'].strip()) < 2:
        errors['first_name'] = "First name too short"
    
    if not data.get('last_name'):
        errors['last_name'] = "Last name is required"
    elif len(data['last_name'].strip()) < 2:
        errors['last_name'] = "Last name too short"
    
    if not data.get('dob'):
        errors['dob'] = "Date of birth is required"
    elif not validate_dob(data['dob']):
        errors['dob'] = "Invalid date of birth"
    
    # Optional fields validation
    if data.get('email') and not validate_email(data['email']):
        errors['email'] = "Invalid email format"
    
    if data.get('phone') and not validate_phone(data['phone']):
        warnings.append("Phone number format may be incorrect")
    
    if data.get('insurance') and not validate_insurance_info(data['insurance'], data.get('member_id')):
        warnings.append("Insurance information format may be incorrect")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

def validate_appointment_data(data: Dict[str, Any], valid_doctors: list) -> Dict[str, Any]:
    """Validate appointment data"""
    errors = {}
    warnings = []
    
    # Required fields
    if not data.get('doctor'):
        errors['doctor'] = "Doctor selection is required"
    elif not validate_doctor_name(data['doctor'], valid_doctors):
        errors['doctor'] = "Invalid doctor selected"
    
    if not data.get('preferred_date'):
        errors['date'] = "Appointment date is required"
    elif not validate_appointment_date(data['preferred_date']):
        errors['date'] = "Invalid appointment date"
    
    # Duration validation
    duration = data.get('duration_minutes', 0)
    if duration not in [30, 60]:
        warnings.append("Unusual appointment duration")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }