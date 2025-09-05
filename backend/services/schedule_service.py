import os
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from ..database.appointment_db import appointment_db
from ..models.appointment import Appointment

logger = logging.getLogger(__name__)

class ScheduleService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.doctor_schedules_path = os.path.join(data_dir, "doctor_schedules.xlsx")
        
        # Available doctors
        self.doctors = ["Dr Asha Rao", "Dr Meera Iyer", "Dr Vikram Gupta"]
        
        # Ensure schedule file exists
        self._ensure_doctor_schedules()

    def _ensure_doctor_schedules(self):
        """Create doctor schedules Excel if it doesn't exist"""
        if not os.path.exists(self.doctor_schedules_path):
            self._create_sample_schedules()

    def _create_sample_schedules(self):
        """Create sample doctor schedules"""
        try:
            # Create sample schedules for next 30 days
            start_date = datetime.now().date()
            dates = [start_date + timedelta(days=i) for i in range(30)]
            
            with pd.ExcelWriter(self.doctor_schedules_path, engine='openpyxl') as writer:
                for doctor in self.doctors:
                    schedule_data = []
                    
                    for date in dates:
                        # Skip weekends for simplicity
                        if date.weekday() < 5:  # Monday = 0, Friday = 4
                            # Morning slots
                            schedule_data.append({
                                'date': date.strftime('%Y-%m-%d'),
                                'start_time': '09:00:00',
                                'end_time': '12:00:00',
                                'slot_duration_default': 30,
                                'available': True
                            })
                            # Afternoon slots
                            schedule_data.append({
                                'date': date.strftime('%Y-%m-%d'),
                                'start_time': '14:00:00',
                                'end_time': '17:00:00',
                                'slot_duration_default': 30,
                                'available': True
                            })
                    
                    df = pd.DataFrame(schedule_data)
                    df.to_excel(writer, sheet_name=doctor, index=False)
            
            logger.info(f"Created sample doctor schedules: {self.doctor_schedules_path}")
            
        except Exception as e:
            logger.error(f"Error creating sample schedules: {e}")

    def get_available_slots(self, doctor: str, preferred_date: str, 
                           duration_minutes: int = 60) -> List[Dict]:
        """Get available time slots for a doctor on a specific date"""
        try:
            # Load doctor's schedule
            if not os.path.exists(self.doctor_schedules_path):
                return []
            
            df = pd.read_excel(self.doctor_schedules_path, sheet_name=doctor)
            
            # Filter by date
            target_date = datetime.strptime(preferred_date, '%Y-%m-%d').date()
            df['date'] = pd.to_datetime(df['date']).dt.date
            day_schedule = df[df['date'] == target_date]
            
            if day_schedule.empty:
                return []
            
            # Get existing appointments for this doctor and date
            existing_appointments = appointment_db.get_appointments_by_doctor_and_date(doctor, preferred_date)
            
            available_slots = []
            
            for _, schedule in day_schedule.iterrows():
                if not schedule.get('available', True):
                    continue
                
                start_time = datetime.combine(target_date, 
                    datetime.strptime(schedule['start_time'], '%H:%M:%S').time())
                end_time = datetime.combine(target_date,
                    datetime.strptime(schedule['end_time'], '%H:%M:%S').time())
                slot_duration = int(schedule.get('slot_duration_default', 30))
                
                # Generate time slots
                current_time = start_time
                while current_time + timedelta(minutes=duration_minutes) <= end_time:
                    slot_end = current_time + timedelta(minutes=duration_minutes)
                    
                    # Check if slot is available (no overlap with existing appointments)
                    is_available = True
                    for appointment in existing_appointments:
                        appt_start = datetime.fromisoformat(appointment.start_time.replace('Z', '+00:00'))
                        appt_end = datetime.fromisoformat(appointment.end_time.replace('Z', '+00:00'))
                        
                        # Remove timezone for comparison
                        appt_start = appt_start.replace(tzinfo=None)
                        appt_end = appt_end.replace(tzinfo=None)
                        
                        # Check for overlap
                        if not (slot_end <= appt_start or current_time >= appt_end):
                            is_available = False
                            break
                    
                    if is_available:
                        available_slots.append({
                            "start_time": current_time.isoformat(),
                            "end_time": slot_end.isoformat(),
                            "duration_minutes": duration_minutes,
                            "doctor": doctor,
                            "formatted_time": current_time.strftime("%I:%M %p")
                        })
                    
                    current_time += timedelta(minutes=slot_duration)
            
            return available_slots[:10]  # Return max 10 slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []

    def find_best_slot(self, doctor: str, preferred_date: str, 
                      duration_minutes: int, time_preference: Optional[Dict] = None) -> Optional[Dict]:
        """Find the best available slot based on preferences"""
        try:
            available_slots = self.get_available_slots(doctor, preferred_date, duration_minutes)
            
            if not available_slots:
                return None
            
            # If no time preference, return first available slot
            if not time_preference:
                return available_slots[0]
            
            # Filter by time preference
            preferred_slots = []
            start_pref = time_preference.get('start', '00:00')
            end_pref = time_preference.get('end', '23:59')
            
            for slot in available_slots:
                slot_time = datetime.fromisoformat(slot['start_time']).time()
                pref_start = datetime.strptime(start_pref, '%H:%M').time()
                pref_end = datetime.strptime(end_pref, '%H:%M').time()
                
                if pref_start <= slot_time <= pref_end:
                    preferred_slots.append(slot)
            
            return preferred_slots[0] if preferred_slots else available_slots[0]
            
        except Exception as e:
            logger.error(f"Error finding best slot: {e}")
            return None

    def get_alternative_dates(self, doctor: str, preferred_date: str, 
                            duration_minutes: int, days_range: int = 7) -> List[Dict]:
        """Get alternative dates if preferred date is not available"""
        try:
            alternatives = []
            start_date = datetime.strptime(preferred_date, '%Y-%m-%d').date()
            
            # Check next few days
            for i in range(1, days_range + 1):
                check_date = start_date + timedelta(days=i)
                
                # Skip weekends
                if check_date.weekday() >= 5:
                    continue
                
                check_date_str = check_date.strftime('%Y-%m-%d')
                slots = self.get_available_slots(doctor, check_date_str, duration_minutes)
                
                if slots:
                    alternatives.append({
                        'date': check_date_str,
                        'formatted_date': check_date.strftime('%A, %B %d, %Y'),
                        'available_slots': len(slots),
                        'first_slot': slots[0]['formatted_time']
                    })
                
                if len(alternatives) >= 3:  # Return max 3 alternatives
                    break
            
            return alternatives
            
        except Exception as e:
            logger.error(f"Error getting alternative dates: {e}")
            return []

    def get_doctor_schedule_summary(self, doctor: str, days_ahead: int = 7) -> Dict:
        """Get summary of doctor's schedule"""
        try:
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=days_ahead)
            
            total_slots = 0
            booked_slots = 0
            
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() < 5:  # Weekdays only
                    date_str = current_date.strftime('%Y-%m-%d')
                    available_slots = self.get_available_slots(doctor, date_str, 30)
                    appointments = appointment_db.get_appointments_by_doctor_and_date(doctor, date_str)
                    
                    # Estimate total slots based on working hours (8 hours, 30-min slots)
                    daily_slots = 16  # 8 hours * 2 slots per hour
                    total_slots += daily_slots
                    booked_slots += len(appointments)
                
                current_date += timedelta(days=1)
            
            available_slots = total_slots - booked_slots
            utilization = (booked_slots / total_slots * 100) if total_slots > 0 else 0
            
            return {
                'doctor': doctor,
                'total_slots': total_slots,
                'booked_slots': booked_slots,
                'available_slots': available_slots,
                'utilization_percent': round(utilization, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting doctor schedule summary: {e}")
            return {}

    def suggest_alternative_doctors(self, preferred_date: str, duration_minutes: int,
                                  exclude_doctor: Optional[str] = None) -> List[Dict]:
        """Suggest alternative doctors with availability"""
        try:
            suggestions = []
            
            for doctor in self.doctors:
                if exclude_doctor and doctor == exclude_doctor:
                    continue
                
                slots = self.get_available_slots(doctor, preferred_date, duration_minutes)
                if slots:
                    suggestions.append({
                        'doctor': doctor,
                        'available_slots': len(slots),
                        'earliest_slot': slots[0]['formatted_time'],
                        'slot_details': slots[0]
                    })
            
            # Sort by number of available slots (descending)
            suggestions.sort(key=lambda x: x['available_slots'], reverse=True)
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting alternative doctors: {e}")
            return []

    def validate_appointment_slot(self, doctor: str, start_time: str, 
                                duration_minutes: int) -> bool:
        """Validate if an appointment slot is still available"""
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            date_str = start_dt.date().strftime('%Y-%m-%d')
            
            # Get existing appointments
            existing_appointments = appointment_db.get_appointments_by_doctor_and_date(doctor, date_str)
            
            # Check for conflicts
            for appointment in existing_appointments:
                appt_start = datetime.fromisoformat(appointment.start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                appt_end = datetime.fromisoformat(appointment.end_time.replace('Z', '+00:00')).replace(tzinfo=None)
                
                # Check for overlap
                if not (end_dt <= appt_start or start_dt >= appt_end):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating appointment slot: {e}")
            return False

# Global instance
schedule_service = ScheduleService()