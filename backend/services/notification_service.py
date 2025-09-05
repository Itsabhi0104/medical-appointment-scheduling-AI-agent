"""
Enhanced notification service with email/SMS support and form distribution
"""
import os
import smtplib
import sqlite3
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.application import MimeApplication
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.logs_dir = "logs"
        self.forms_dir = "forms"
        
        # Email configuration
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_user = os.getenv("EMAIL_USER")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.email_user)
        
        # SMS configuration (using a service like Twilio)
        self.twilio_sid = os.getenv("TWILIO_SID")
        self.twilio_token = os.getenv("TWILIO_TOKEN")
        self.twilio_phone = os.getenv("TWILIO_PHONE")
        
        # Paths
        self.notifications_log = os.path.join(self.logs_dir, "notifications.log")
        self.intake_form_path = os.path.join(self.forms_dir, "New Patient Intake Form.pdf")
        self.appointments_db = os.path.join(data_dir, "appointments.db")
        
        # Ensure directories exist
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.forms_dir, exist_ok=True)

    def _log_notification(self, message: str, level: str = "INFO"):
        """Log notification with timestamp"""
        timestamp = datetime.now().isoformat()
        log_message = f"[{timestamp}] [{level}] {message}"
        
        # Write to file
        with open(self.notifications_log, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
        
        # Also log to console
        logger.info(log_message)
        print(f"[NOTIFICATION] {message}")

    def send_email(self, to_email: str, subject: str, body: str, 
                   attachments: Optional[List[str]] = None, 
                   html_body: Optional[str] = None) -> Dict:
        """Send email notification"""
        try:
            if not self.email_user or not self.email_password:
                self._log_notification(f"📧 EMAIL SIMULATION: To: {to_email}, Subject: {subject}", "SIMULATION")
                return {"success": True, "simulated": True, "message": "Email simulated (no SMTP config)"}
            
            # Create message
            msg = MimeMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text body
            if body:
                text_part = MimeText(body, 'plain')
                msg.attach(text_part)
            
            # Add HTML body
            if html_body:
                html_part = MimeText(html_body, 'html')
                msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            attach = MimeApplication(f.read(), _subtype="pdf")
                            attach.add_header('Content-Disposition', 'attachment', 
                                            filename=os.path.basename(file_path))
                            msg.attach(attach)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()
            
            self._log_notification(f"📧 Email sent to {to_email}: {subject}")
            return {"success": True, "message": "Email sent successfully"}
            
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            self._log_notification(error_msg, "ERROR")
            # Simulate for demo purposes
            self._log_notification(f"📧 EMAIL SIMULATION: To: {to_email}, Subject: {subject}", "SIMULATION")
            return {"success": True, "simulated": True, "error": str(e)}

    def send_sms(self, to_phone: str, message: str) -> Dict:
        """Send SMS notification"""
        try:
            if not self.twilio_sid or not self.twilio_token:
                self._log_notification(f"📱 SMS SIMULATION: To: {to_phone}, Message: {message[:50]}...", "SIMULATION")
                return {"success": True, "simulated": True, "message": "SMS simulated (no Twilio config)"}
            
            # Use Twilio API
            from twilio.rest import Client
            client = Client(self.twilio_sid, self.twilio_token)
            
            twilio_message = client.messages.create(
                body=message,
                from_=self.twilio_phone,
                to=to_phone
            )
            
            self._log_notification(f"📱 SMS sent to {to_phone}: {message[:50]}...")
            return {"success": True, "message_sid": twilio_message.sid}
            
        except ImportError:
            # Twilio not installed, simulate
            self._log_notification(f"📱 SMS SIMULATION: To: {to_phone}, Message: {message[:50]}...", "SIMULATION")
            return {"success": True, "simulated": True, "message": "SMS simulated (Twilio not installed)"}
        except Exception as e:
            error_msg = f"Failed to send SMS to {to_phone}: {str(e)}"
            self._log_notification(error_msg, "ERROR")
            # Simulate for demo
            self._log_notification(f"📱 SMS SIMULATION: To: {to_phone}, Message: {message[:50]}...", "SIMULATION")
            return {"success": True, "simulated": True, "error": str(e)}

    def send_confirmation(self, appointment: Dict, patient: Dict, 
                         include_form: bool = True) -> Dict:
        """Send appointment confirmation"""
        try:
            patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()
            doctor = appointment.get('doctor', 'your doctor')
            start_time = appointment.get('start_time', '')
            appointment_id = appointment.get('appointment_id', '')
            
            # Format start time
            try:
                start_dt = pd.to_datetime(start_time)
                formatted_time = start_dt.strftime("%A, %B %d, %Y at %I:%M %p")
            except:
                formatted_time = start_time
            
            # Email content
            subject = f"Appointment Confirmation - {appointment_id}"
            
            text_body = f"""
Dear {patient_name},

Your appointment has been confirmed!

Appointment Details:
- Doctor: {doctor}
- Date & Time: {formatted_time}
- Appointment ID: {appointment_id}

Please arrive 15 minutes early for check-in.

If you need to reschedule or cancel, please contact us at least 24 hours in advance.

Best regards,
Medical Clinic Team
"""
            
            html_body = f"""
<html>
<body>
    <h2>Appointment Confirmation</h2>
    <p>Dear <strong>{patient_name}</strong>,</p>
    
    <p>Your appointment has been confirmed!</p>
    
    <div style="background-color: #f0f8ff; padding: 15px; border-radius: 5px;">
        <h3>Appointment Details:</h3>
        <ul>
            <li><strong>Doctor:</strong> {doctor}</li>
            <li><strong>Date & Time:</strong> {formatted_time}</li>
            <li><strong>Appointment ID:</strong> {appointment_id}</li>
        </ul>
    </div>
    
    <p><strong>Important:</strong> Please arrive 15 minutes early for check-in.</p>
    
    <p>If you need to reschedule or cancel, please contact us at least 24 hours in advance.</p>
    
    <p>Best regards,<br>Medical Clinic Team</p>
</body>
</html>
"""
            
            # Prepare attachments
            attachments = []
            if include_form and os.path.exists(self.intake_form_path):
                attachments.append(self.intake_form_path)
            
            # Send email
            email_result = {"success": False}
            if patient.get('email'):
                email_result = self.send_email(
                    patient['email'], subject, text_body, 
                    attachments=attachments, html_body=html_body
                )
            
            # Send SMS
            sms_result = {"success": False}
            if patient.get('phone'):
                sms_message = f"Appointment confirmed with {doctor} on {formatted_time}. ID: {appointment_id}. Please arrive 15 min early."
                sms_result = self.send_sms(patient['phone'], sms_message)
            
            # Update appointment record
            self._update_form_sent_status(appointment_id, include_form)
            
            return {
                "success": True,
                "email_result": email_result,
                "sms_result": sms_result,
                "form_attached": include_form and os.path.exists(self.intake_form_path)
            }
            
        except Exception as e:
            error_msg = f"Failed to send confirmation for {appointment_id}: {str(e)}"
            self._log_notification(error_msg, "ERROR")
            return {"success": False, "error": str(e)}

    def send_reminder(self, appointment: Dict, patient: Dict, 
                     reminder_type: str = "first") -> Dict:
        """Send appointment reminder"""
        try:
            patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()
            doctor = appointment.get('doctor', 'your doctor')
            start_time = appointment.get('start_time', '')
            appointment_id = appointment.get('appointment_id', '')
            
            # Format start time
            try:
                start_dt = pd.to_datetime(start_time)
                formatted_time = start_dt.strftime("%A, %B %d, %Y at %I:%M %p")
                days_until = (start_dt.date() - datetime.now().date()).days
            except:
                formatted_time = start_time
                days_until = 0
            
            # Customize message based on reminder type
            if reminder_type == "first":
                subject = f"Appointment Reminder - {appointment_id}"
                reminder_text = f"This is a reminder that you have an appointment in {days_until} days."
                questions = ""
            elif reminder_type == "second":
                subject = f"Important: Appointment in 24 Hours - {appointment_id}"
                reminder_text = f"Your appointment is tomorrow! Please confirm your attendance."
                questions = """
Please reply to confirm:
1. Have you filled out your intake forms?
2. Will you be attending this appointment?
"""
            else:  # third/final
                subject = f"Final Reminder: Appointment Today - {appointment_id}"
                reminder_text = f"Your appointment is today! Please arrive 15 minutes early."
                questions = """
If you need to cancel, please call immediately:
1. Are you planning to attend?
2. If not, please provide reason for cancellation.
"""
            
            # Email content
            text_body = f"""
Dear {patient_name},

{reminder_text}

Appointment Details:
- Doctor: {doctor}
- Date & Time: {formatted_time}
- Appointment ID: {appointment_id}

{questions}

Best regards,
Medical Clinic Team
"""
            
            # Send notifications
            email_result = {"success": False}
            if patient.get('email'):
                email_result = self.send_email(patient['email'], subject, text_body)
            
            sms_result = {"success": False}
            if patient.get('phone'):
                sms_message = f"Reminder: Appointment with {doctor} on {formatted_time}. ID: {appointment_id}."
                if reminder_type != "first":
                    sms_message += " Please confirm attendance."
                sms_result = self.send_sms(patient['phone'], sms_message)
            
            # Log reminder
            self._log_notification(f"📅 {reminder_type.upper()} reminder sent for {appointment_id}")
            
            return {
                "success": True,
                "reminder_type": reminder_type,
                "email_result": email_result,
                "sms_result": sms_result
            }
            
        except Exception as e:
            error_msg = f"Failed to send {reminder_type} reminder for {appointment_id}: {str(e)}"
            self._log_notification(error_msg, "ERROR")
            return {"success": False, "error": str(e)}

    def _update_form_sent_status(self, appointment_id: str, form_sent: bool):
        """Update form sent status in database"""
        try:
            if os.path.exists(self.appointments_db):
                conn = sqlite3.connect(self.appointments_db)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE appointments SET form_sent = ? WHERE appointment_id = ?",
                    (1 if form_sent else 0, appointment_id)
                )
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Error updating form sent status: {e}")

    def get_pending_reminders(self) -> List[Dict]:
        """Get appointments that need reminders"""
        try:
            if not os.path.exists(self.appointments_db):
                return []
            
            conn = sqlite3.connect(self.appointments_db)
            conn.row_factory = sqlite3.Row
            
            # Get appointments in next 3 days
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, p.first_name, p.last_name, p.email, p.phone
                FROM appointments a
                LEFT JOIN patients p ON a.patient_id = p.patient_id
                WHERE a.status = 'confirmed' 
                AND datetime(a.start_time) > datetime('now')
                AND datetime(a.start_time) <= datetime('now', '+3 days')
                ORDER BY a.start_time
            """)
            
            appointments = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting pending reminders: {e}")
            return []

    def process_reminder_queue(self) -> Dict:
        """Process reminder queue and send appropriate reminders"""
        try:
            pending = self.get_pending_reminders()
            processed = {"first": 0, "second": 0, "third": 0, "errors": 0}
            
            now = datetime.now()
            
            for appointment in pending:
                try:
                    start_dt = pd.to_datetime(appointment['start_time'])
                    hours_until = (start_dt - now).total_seconds() / 3600
                    
                    # Determine reminder type based on time until appointment
                    if 48 <= hours_until <= 72:  # 2-3 days before
                        reminder_type = "first"
                    elif 12 <= hours_until <= 24:  # 12-24 hours before
                        reminder_type = "second"
                    elif 0 <= hours_until <= 4:  # Day of appointment
                        reminder_type = "third"
                    else:
                        continue  # Skip if not in reminder window
                    
                    # Send reminder
                    result = self.send_reminder(appointment, appointment, reminder_type