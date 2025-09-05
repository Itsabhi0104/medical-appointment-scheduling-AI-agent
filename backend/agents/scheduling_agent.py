import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging
from ..database.patient_db import patient_db
from ..database.appointment_db import appointment_db
from ..models.patient import Patient
from ..models.appointment import Appointment
from ..utils.date_utils import (
    get_current_ist, generate_time_slots, 
    is_slot_available, add_minutes_to_datetime
)
from ..utils.validation import validate_patient_data, validate_appointment_data
from ..utils.config import config

logger = logging.getLogger(__name__)

class SchedulingAgent:
    def __init__(self):
        self.doctors = config.DOCTORS
        
    def lookup_or_create_patient(self, patient_data: Dict[str, Any]) -> Tuple[Optional[Patient], bool, List[str]]:
        """Lookup existing patient or create new one
        Returns: (Patient object, is_new_patient, errors)
        """
        errors = []
        
        # Validate patient data
        validation = validate_patient_data(patient_data)
        if not validation['valid']:
            return None, False, list(validation['errors'].values())
        
        first_name = patient_data['first_name'].strip()
        last_name = patient_data['last_name'].strip()
        dob = patient_data['dob']
        
        # Try to find existing patient
        existing_patient = patient_db.find_patient_by_details(first_name, last_name, dob)
        
        if existing_patient:
            # Update patient info if new data provided
            updates = {}
            if patient_data.get('email') and patient_data['email'] != existing_patient.email:
                updates['email'] = patient_data['email']
            if patient_data.get('phone') and patient_data['phone'] != existing_patient.phone:
                updates['phone'] = patient_data['phone']
            if patient_data.get('insurance') and patient_data['insurance'] != existing_patient.insurance_company:
                updates['insurance_company'] = patient_data['insurance']
            if patient_data.get('member_id') and patient_data['member_id'] != existing_patient.member_id:
                updates['member_id'] = patient_data['member_id']
            
            if updates:
                patient_db.update_patient(existing_patient.patient_id, updates)
                # Refresh patient data
                existing_patient = patient_db.get_patient_by_id(existing_patient.patient_id)
            
            logger.info(f"Found existing patient: {existing_patient.patient_id}")
            return existing_patient, False, []
        
        # Create new patient
        try:
            new_patient = Patient(
                patient_id=f"P{uuid.uuid4().hex[:8].upper()}",
                first_name=first_name,
                last_name=last_name,
                dob=dob,
                phone=patient_data.get('phone'),
                email=patient_data.get('email'),
                insurance_company=patient_data.get('insurance'),
                member_id=patient_data.get('member_id'),
                is_returning=False,
                created_at=get_current_ist().isoformat()
            )
            
            success = patient_db.create_patient(new_patient)
            if success:
                logger.info(f"Created new patient: {new_patient.patient_id}")
                return new_patient, True, []
            else:
                return None, False, ["Failed to create patient record"]
                
        except Exception as e:
            logger.error(f"Error creating patient: {e}")
            return None, False, [f"Error creating patient: {str(e)}"]
    
    def get_available_slots(self, doctor: str, date: str, duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get available time slots for doctor on specific date"""
        try:
            # Generate all possible slots
            all_slots = generate_time_slots(date, config.CLINIC_START_HOUR, config.CLINIC_END_HOUR)
            
            # Get existing appointments for this doctor on this date
            existing_appointments = appointment_db.get_appointments_by_doctor_and_date(doctor, date)
            
            # Convert to (start_time, end_time) tuples
            booked_slots = [
                (apt.start_time, apt.end_time) 
                for apt in existing_appointments
                if apt.status not in ['cancelled']
            ]
            
            # Filter available slots
            available_slots = []
            for slot_time in all_slots:
                if is_slot_available(slot_time, booked_slots, duration_minutes):
                    end_time = add_minutes_to_datetime(slot_time, duration_minutes)
                    
                    # Format for display
                    slot_dt = datetime.fromisoformat(slot_time.replace('Z', '+00:00'))
                    display_time = slot_dt.strftime("%I:%M %p")
                    
                    available_slots.append({
                        'start_time': slot_time,
                        'end_time': end_time,
                        'display_time': display_time,
                        'duration_minutes': duration_minutes
                    })
            
            logger.info(f"Found {len(available_slots)} available slots for {doctor} on {date}")
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []
    
    def create_appointment(self, patient: Patient, appointment_data: Dict[str, Any]) -> Tuple[Optional[Appointment], List[str]]:
        """Create a new appointment"""
        errors = []
        
        # Validate appointment data
        validation = validate_appointment_data(appointment_data, self.doctors)
        if not validation['valid']:
            return None, list(validation['errors'].values())
        
        try:
            # Determine appointment duration based on patient type
            is_new_patient = not patient.is_returning
            duration = config.NEW_PATIENT_DURATION if is_new_patient else config.RETURNING_PATIENT_DURATION
            
            # Override if specific duration requested
            if appointment_data.get('duration_minutes'):
                duration = appointment_data['duration_minutes']
            
            # Get available slots
            doctor = appointment_data['doctor']
            date = appointment_data['preferred_date']
            available_slots = self.get_available_slots(doctor, date, duration)
            
            if not available_slots:
                return None, ["No available slots for the requested date and doctor"]
            
            # If specific time requested, try to find matching slot
            selected_slot = None
            if appointment_data.get('preferred_time'):
                preferred_time = appointment_data['preferred_time']
                for slot in available_slots:
                    if preferred_time in slot['display_time']:
                        selected_slot = slot
                        break
            
            # Otherwise, use first available slot
            if not selected_slot:
                selected_slot = available_slots[0]
            
            # Create appointment
            appointment = Appointment(
                appointment_id=f"A{uuid.uuid4().hex[:8]}",
                patient_id=patient.patient_id,
                doctor=doctor,
                start_time=selected_slot['start_time'],
                end_time=selected_slot['end_time'],
                duration_minutes=duration,
                status="scheduled",
                reason=appointment_data.get('reason', 'consultation'),
                form_sent=False,
                calendly_url=None,
                created_at=get_current_ist().isoformat()
            )
            
            success = appointment_db.create_appointment(appointment)
            if success:
                # Update patient as returning
                patient_db.update_patient(patient.patient_id, {
                    'is_returning': True,
                    'last_appointment': appointment.start_time
                })
                
                logger.info(f"Created appointment: {appointment.appointment_id}")
                return appointment, []
            else:
                return None, ["Failed to create appointment"]
                
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return None, [f"Error creating appointment: {str(e)}"]
    
    def get_suggested_slots(self, doctor: str, preferred_date: str, 
                          time_window: Optional[Dict] = None, 
                          duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get suggested available slots with preference matching"""
        
        slots = []
        
        # Try the preferred date first
        date_slots = self.get_available_slots(doctor, preferred_date, duration_minutes)
        
        # Filter by time window if specified
        if time_window and date_slots:
            start_hour = int(time_window.get('start', '09:00').split(':')[0])
            end_hour = int(time_window.get('end', '17:00').split(':')[0])
            
            filtered_slots = []
            for slot in date_slots:
                slot_hour = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).hour
                if start_hour <= slot_hour < end_hour:
                    filtered_slots.append(slot)
            
            date_slots = filtered_slots
        
        slots.extend(date_slots[:3])  # Top 3 slots for preferred date
        
        # If not enough slots, check next few days
        if len(slots) < 3:
            base_date = datetime.strptime(preferred_date, "%Y-%m-%d")
            
            for i in range(1, 8):  # Check next 7 days
                next_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                next_slots = self.get_available_slots(doctor, next_date, duration_minutes)
                
                if time_window and next_slots:
                    start_hour = int(time_window.get('start', '09:00').split(':')[0])
                    end_hour = int(time_window.get('end', '17:00').split(':')[0])
                    
                    filtered_slots = []
                    for slot in next_slots:
                        slot_hour = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).hour
                        if start_hour <= slot_hour < end_hour:
                            filtered_slots.append(slot)
                    
                    next_slots = filtered_slots
                
                slots.extend(next_slots[:2])  # Add up to 2 slots per day
                
                if len(slots) >= 5:  # Limit total suggestions
                    break
        
        return slots[:5]  # Return max 5 suggestions
    
    def reschedule_appointment(self, appointment_id: str, new_date: str, 
                             new_time: Optional[str] = None) -> Tuple[bool, List[str]]:
        """Reschedule an existing appointment"""
        try:
            appointment = appointment_db.get_appointment_by_id(appointment_id)
            if not appointment:
                return False, ["Appointment not found"]
            
            # Get available slots for new date
            available_slots = self.get_available_slots(
                appointment.doctor, new_date, appointment.duration_minutes
            )
            
            if not available_slots:
                return False, ["No available slots for the requested date"]
            
            # Select slot
            selected_slot = available_slots[0]  # Default to first available
            if new_time:
                for slot in available_slots:
                    if new_time in slot['display_time']:
                        selected_slot = slot
                        break
            
            # Update appointment
            updates = {
                'start_time': selected_slot['start_time'],
                'end_time': selected_slot['end_time'],
                'updated_at': get_current_ist().isoformat()
            }
            
            success = appointment_db.update_appointment(appointment_id, updates)
            if success:
                logger.info(f"Rescheduled appointment: {appointment_id}")
                return True, []
            else:
                return False, ["Failed to update appointment"]
                
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}")
            return False, [f"Error rescheduling: {str(e)}"]

# Global instance
scheduling_agent = SchedulingAgent()