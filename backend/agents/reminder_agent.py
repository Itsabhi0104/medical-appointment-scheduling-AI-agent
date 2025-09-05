import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from ..database.reminder_db import reminder_db
from ..database.appointment_db import appointment_db
from ..database.patient_db import patient_db
from ..models.reminder import Reminder
from ..utils.date_utils import get_current_ist, get_reminder_times

logger = logging.getLogger(__name__)

class ReminderAgent:
    def __init__(self):
        pass
    
    def create_appointment_reminders(self, appointment_id: str) -> List[Reminder]:
        """Create 3 automated reminders for an appointment"""
        reminders = []
        
        try:
            appointment = appointment_db.get_appointment_by_id(appointment_id)
            if not appointment:
                logger.error(f"Appointment not found: {appointment_id}")
                return []
            
            # Calculate reminder times (24h, 4h, 1h before)
            reminder_times = get_reminder_times(appointment.start_time)
            reminder_types = ["first", "second", "third"]
            
            for i, (reminder_time, reminder_type) in enumerate(zip(reminder_times, reminder_types)):
                reminder = Reminder(
                    reminder_id=f"R{uuid.uuid4().hex[:8]}",
                    appointment_id=appointment_id,
                    reminder_type=reminder_type,
                    scheduled_time=reminder_time,
                    status="pending",
                    created_at=get_current_ist().isoformat()
                )
                
                success = reminder_db.create_reminder(reminder)
                if success:
                    reminders.append(reminder)
                    logger.info(f"Created {reminder_type} reminder: {reminder.reminder_id}")
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error creating reminders: {e}")
            return []
    
    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """Get reminders that need to be sent now"""
        try:
            pending_reminders = reminder_db.get_pending_reminders()
            
            enriched_reminders = []
            for reminder in pending_reminders:
                # Get appointment and patient details
                appointment = appointment_db.get_appointment_by_id(reminder.appointment_id)
                if not appointment:
                    continue
                
                patient = patient_db.get_patient_by_id(appointment.patient_id)
                if not patient:
                    continue
                
                # Skip if appointment is cancelled
                if appointment.status == 'cancelled':
                    continue
                
                enriched_reminders.append({
                    'reminder': reminder,
                    'appointment': appointment,
                    'patient': patient,
                    'reminder_content': self._generate_reminder_content(reminder, appointment, patient)
                })
            
            return enriched_reminders
            
        except Exception as e:
            logger.error(f"Error getting pending reminders: {e}")
            return []
    
    def _generate_reminder_content(self, reminder: Reminder, appointment, patient) -> Dict[str, str]:
        """Generate reminder content based on reminder type"""
        
        # Format appointment time
        apt_time = datetime.fromisoformat(appointment.start_time.replace('Z', '+00:00'))
        formatted_time = apt_time.strftime("%B %d, %Y at %I:%M %p")
        
        # Base content
        base_info = {
            'patient_name': patient.full_name,
            'doctor': appointment.doctor,
            'appointment_time': formatted_time,
            'appointment_id': appointment.appointment_id
        }
        
        if reminder.reminder_type == "first":
            # Simple reminder - 24h before
            return {
                'subject': 'Appointment Reminder - Tomorrow',
                'message': f"""
Dear {patient.full_name},

This is a reminder about your upcoming appointment:

• Doctor: {appointment.doctor}
• Date & Time: {formatted_time}
• Appointment ID: {appointment.appointment_id}

Please make sure to arrive 15 minutes early for check-in.

If you need to reschedule, please contact us as soon as possible.

Best regards,
Medical Clinic
""",
                'type': 'simple_reminder',
                **base_info
            }
        
        elif reminder.reminder_type == "second":
            # Action reminder - 4h before (ask about forms)
            return {
                'subject': 'Appointment Today - Action Required',
                'message': f"""
Dear {patient.full_name},

Your appointment is in a few hours:

• Doctor: {appointment.doctor}
• Date & Time: {formatted_time}
• Appointment ID: {appointment.appointment_id}

IMPORTANT QUESTIONS:
1. Have you filled out the intake forms that were sent to you?
2. Do you confirm your visit today?

Please reply to this email with:
- "FORMS COMPLETED: Yes/No"
- "VISIT CONFIRMED: Yes/No"
- If not confirmed, please mention the reason for cancellation.

Best regards,
Medical Clinic
""",
                'type': 'action_reminder',
                **base_info
            }
        
        elif reminder.reminder_type == "third":
            # Final reminder - 1h before (last chance)
            return {
                'subject': 'Final Reminder - Appointment in 1 Hour',
                'message': f"""
Dear {patient.full_name},

FINAL REMINDER: Your appointment is in 1 hour!

• Doctor: {appointment.doctor}
• Date & Time: {formatted_time}
• Appointment ID: {appointment.appointment_id}

URGENT - Please confirm:
1. Have you filled the intake forms?
2. Are you still coming for your appointment?

If you cannot attend, please call us immediately or reply:
- "FORMS COMPLETED: Yes/No" 
- "VISIT CONFIRMED: Yes/No"
- If cancelling, please provide reason.

We're expecting you in 1 hour!

Best regards,
Medical Clinic
""",
                'type': 'final_reminder',
                **base_info
            }
        
        return {'subject': 'Appointment Reminder', 'message': 'Please check your appointment details.'}
    
    def mark_reminder_sent(self, reminder_id: str, email_sent: bool = False, sms_sent: bool = False) -> bool:
        """Mark reminder as sent"""
        try:
            updates = {
                'status': 'sent',
                'email_sent': email_sent,
                'sms_sent': sms_sent,
                'sent_at': get_current_ist().isoformat()
            }
            
            success = reminder_db.update_reminder(reminder_id, updates)
            if success:
                logger.info(f"Marked reminder as sent: {reminder_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error marking reminder as sent: {e}")
            return False
    
    def record_patient_response(self, reminder_id: str, response_text: str) -> bool:
        """Record patient response to reminder"""
        try:
            # Parse response for key information
            response_lower = response_text.lower()
            
            # Extract forms completion status
            forms_completed = None
            if 'forms completed: yes' in response_lower:
                forms_completed = True
            elif 'forms completed: no' in response_lower:
                forms_completed = False
            
            # Extract visit confirmation
            visit_confirmed = None
            if 'visit confirmed: yes' in response_lower:
                visit_confirmed = True
            elif 'visit confirmed: no' in response_lower:
                visit_confirmed = False
            
            # Record response
            success = reminder_db.record_patient_response(reminder_id, response_text)
            
            if success:
                # Get reminder and appointment details
                reminder = reminder_db.get_reminders_by_appointment("dummy")[0]  # This needs fixing
                # Update appointment status based on response
                if visit_confirmed is False:
                    # Patient cancelled - update appointment
                    appointment_db.update_appointment(reminder.appointment_id, {
                        'status': 'cancelled',
                        'updated_at': get_current_ist().isoformat()
                    })
                
                logger.info(f"Recorded patient response for reminder: {reminder_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error recording patient response: {e}")
            return False
    
    def get_reminder_stats(self, days_back: int = 30) -> Dict[str, Any]:
        """Get reminder statistics"""
        try:
            # This would need to be implemented with proper database queries
            # For now, return basic stats
            return {
                'total_sent': 0,
                'response_rate': 0.0,
                'cancellation_rate': 0.0,
                'forms_completion_rate': 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting reminder stats: {e}")
            return {}
    
    def cleanup_old_reminders(self, days_old: int = 30) -> int:
        """Clean up old completed reminders"""
        try:
            # Implementation would delete old reminders
            # For now, return 0
            return 0
            
        except Exception as e:
            logger.error(f"Error cleaning up reminders: {e}")
            return 0

# Global instance
reminder_agent = ReminderAgent()