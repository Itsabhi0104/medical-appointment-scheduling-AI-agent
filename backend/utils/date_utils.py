from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import pytz

def get_ist_timezone():
    """Get IST timezone"""
    return pytz.timezone('Asia/Kolkata')

def get_current_ist():
    """Get current IST datetime"""
    return datetime.now(get_ist_timezone())

def format_datetime_for_display(dt_str: str) -> str:
    """Format datetime for user display"""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        return dt_str

def get_next_weekday(weekday: int, start_date: datetime = None) -> datetime:
    """Get next occurrence of weekday (0=Monday, 6=Sunday)"""
    if start_date is None:
        start_date = get_current_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    
    days_ahead = weekday - start_date.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    
    return start_date + timedelta(days=days_ahead)

def generate_time_slots(date: str, start_hour: int = 9, end_hour: int = 17) -> List[str]:
    """Generate available time slots for a date"""
    slots = []
    base_date = datetime.strptime(date, "%Y-%m-%d")
    
    for hour in range(start_hour, end_hour):
        for minute in [0, 30]:  # 30-minute intervals
            slot_time = base_date.replace(hour=hour, minute=minute)
            # Convert to IST
            ist_tz = get_ist_timezone()
            slot_time = ist_tz.localize(slot_time)
            slots.append(slot_time.isoformat())
    
    return slots

def is_slot_available(slot_time: str, booked_slots: List[Tuple[str, str]], duration_minutes: int = 30) -> bool:
    """Check if a time slot is available"""
    try:
        slot_dt = datetime.fromisoformat(slot_time.replace('Z', '+00:00'))
        slot_end = slot_dt + timedelta(minutes=duration_minutes)
        
        for booked_start, booked_end in booked_slots:
            booked_start_dt = datetime.fromisoformat(booked_start.replace('Z', '+00:00'))
            booked_end_dt = datetime.fromisoformat(booked_end.replace('Z', '+00:00'))
            
            # Check for overlap
            if (slot_dt < booked_end_dt and slot_end > booked_start_dt):
                return False
        
        return True
    except:
        return False

def add_minutes_to_datetime(dt_str: str, minutes: int) -> str:
    """Add minutes to datetime string"""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        new_dt = dt + timedelta(minutes=minutes)
        return new_dt.isoformat()
    except:
        return dt_str

def get_reminder_times(appointment_time: str) -> List[str]:
    """Calculate reminder times (24h, 4h, 1h before)"""
    try:
        apt_dt = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
        
        reminders = [
            (apt_dt - timedelta(hours=24)).isoformat(),  # 24h before
            (apt_dt - timedelta(hours=4)).isoformat(),   # 4h before
            (apt_dt - timedelta(hours=1)).isoformat(),   # 1h before
        ]
        
        return reminders
    except:
        return []

def is_business_hours(dt_str: str, start_hour: int = 9, end_hour: int = 17) -> bool:
    """Check if datetime is within business hours"""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        hour = dt.hour
        weekday = dt.weekday()
        
        # Monday=0, Sunday=6 (exclude weekends)
        return (weekday < 5 and start_hour <= hour < end_hour)
    except:
        return False