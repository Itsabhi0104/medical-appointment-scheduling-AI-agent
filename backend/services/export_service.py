import os
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..database.appointment_db import appointment_db
from ..database.patient_db import patient_db
from ..database.reminder_db import reminder_db
import logging

logger = logging.getLogger(__name__)

class ExportService:
    def __init__(self, export_dir: str = "exports"):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)

    def export_daily_bookings(self, date: Optional[str] = None) -> str:
        """Export daily bookings to Excel"""
        try:
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # Get appointments for the date
            appointments = []
            for doctor in ["Dr Asha Rao", "Dr Meera Iyer", "Dr Vikram Gupta"]:
                doctor_appointments = appointment_db.get_appointments_by_doctor_and_date(doctor, date)
                appointments.extend(doctor_appointments)
            
            if not appointments:
                logger.warning(f"No appointments found for {date}")
                return ""
            
            # Prepare export data
            export_data = []
            for appointment in appointments:
                patient = patient_db.get_patient_by_id(appointment.patient_id)
                
                if patient:
                    export_data.append({
                        'Date': date,
                        'Appointment ID': appointment.appointment_id,
                        'Patient Name': patient.full_name,
                        'Patient ID': patient.patient_id,
                        'Doctor': appointment.doctor,
                        'Start Time': appointment.start_time,
                        'Duration (mins)': appointment.duration_minutes,
                        'Status': appointment.status,
                        'Reason': appointment.reason or '',
                        'Patient Type': 'Returning' if patient.is_returning else 'New',
                        'Insurance': patient.insurance_company or '',
                        'Member ID': patient.member_id or '',
                        'Email': patient.email or '',
                        'Phone': patient.phone or '',
                        'Form Sent': 'Yes' if appointment.form_sent else 'No',
                        'Calendly URL': appointment.calendly_url or '',
                        'Created At': appointment.created_at
                    })
            
            # Create Excel file
            filename = f"bookings_{date.replace('-', '')}.xlsx"
            filepath = os.path.join(self.export_dir, filename)
            
            df = pd.DataFrame(export_data)
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            logger.info(f"Exported daily bookings: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting daily bookings: {e}")
            return ""

    def export_patient_summary(self) -> str:
        """Export patient summary"""
        try:
            patients = patient_db.get_all_patients()
            
            if not patients:
                return ""
            
            export_data = []
            for patient in patients:
                # Get patient's appointments
                appointments = appointment_db.get_appointments_by_patient(patient.patient_id)
                
                export_data.append({
                    'Patient ID': patient.patient_id,
                    'Name': patient.full_name,
                    'DOB': patient.dob,
                    'Email': patient.email or '',
                    'Phone': patient.phone or '',
                    'Insurance': patient.insurance_company or '',
                    'Member ID': patient.member_id or '',
                    'Patient Type': 'Returning' if patient.is_returning else 'New',
                    'Total Appointments': len(appointments),
                    'Last Appointment': appointments[0].start_time if appointments else '',
                    'Registered Date': patient.created_at
                })
            
            filename = f"patient_summary_{datetime.now().strftime('%Y%m%d')}.xlsx"
            filepath = os.path.join(self.export_dir, filename)
            
            df = pd.DataFrame(export_data)
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            logger.info(f"Exported patient summary: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting patient summary: {e}")
            return ""

    def export_doctor_schedule_report(self, days_ahead: int = 7) -> str:
        """Export doctor schedule report"""
        try:
            doctors = ["Dr Asha Rao", "Dr Meera Iyer", "Dr Vikram Gupta"]
            end_date = datetime.now() + timedelta(days=days_ahead)
            
            export_data = []
            
            for doctor in doctors:
                # Get appointments for this doctor
                all_appointments = appointment_db.get_all_appointments(days_ahead)
                doctor_appointments = [a for a in all_appointments if a.doctor == doctor]
                
                # Calculate statistics
                total_appointments = len(doctor_appointments)
                confirmed = len([a for a in doctor_appointments if a.status == 'confirmed'])
                scheduled = len([a for a in doctor_appointments if a.status == 'scheduled'])
                cancelled = len([a for a in doctor_appointments if a.status == 'cancelled'])
                
                # Upcoming appointments
                now = datetime.now()
                upcoming = [a for a in doctor_appointments 
                           if datetime.fromisoformat(a.start_time.replace('Z', '+00:00')) > now]
                
                export_data.append({
                    'Doctor': doctor,
                    'Total Appointments': total_appointments,
                    'Confirmed': confirmed,
                    'Scheduled': scheduled,
                    'Cancelled': cancelled,
                    'Upcoming': len(upcoming),
                    'Next Appointment': upcoming[0].start_time if upcoming else 'None',
                    'Report Generated': datetime.now().isoformat()
                })
            
            filename = f"doctor_schedule_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
            filepath = os.path.join(self.export_dir, filename)
            
            df = pd.DataFrame(export_data)
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            logger.info(f"Exported doctor schedule report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting doctor schedule report: {e}")
            return ""

    def export_reminder_report(self) -> str:
        """Export reminder activity report"""
        try:
            # Get all appointments with reminders
            appointments = appointment_db.get_all_appointments(30)
            
            export_data = []
            for appointment in appointments:
                patient = patient_db.get_patient_by_id(appointment.patient_id)
                reminders = reminder_db.get_reminders_by_appointment(appointment.appointment_id)
                
                if patient:
                    for reminder in reminders:
                        export_data.append({
                            'Appointment ID': appointment.appointment_id,
                            'Patient Name': patient.full_name,
                            'Doctor': appointment.doctor,
                            'Appointment Date': appointment.start_time,
                            'Reminder Type': reminder.reminder_type,
                            'Scheduled Time': reminder.scheduled_time,
                            'Status': reminder.status,
                            'Email Sent': 'Yes' if reminder.email_sent else 'No',
                            'SMS Sent': 'Yes' if reminder.sms_sent else 'No',
                            'Response Received': 'Yes' if reminder.response_received else 'No',
                            'Patient Response': reminder.patient_response or '',
                            'Sent At': reminder.sent_at or ''
                        })
            
            if not export_data:
                logger.warning("No reminder data found")
                return ""
            
            filename = f"reminder_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
            filepath = os.path.join(self.export_dir, filename)
            
            df = pd.DataFrame(export_data)
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            logger.info(f"Exported reminder report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting reminder report: {e}")
            return ""

    def export_comprehensive_report(self) -> str:
        """Export comprehensive admin report"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"comprehensive_report_{timestamp}.xlsx"
            filepath = os.path.join(self.export_dir, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Sheet 1: Recent Appointments
                appointments = appointment_db.get_all_appointments(30)
                if appointments:
                    appointments_data = []
                    for appointment in appointments:
                        patient = patient_db.get_patient_by_id(appointment.patient_id)
                        if patient:
                            appointments_data.append({
                                'Appointment ID': appointment.appointment_id,
                                'Patient Name': patient.full_name,
                                'Doctor': appointment.doctor,
                                'Start Time': appointment.start_time,
                                'Duration': appointment.duration_minutes,
                                'Status': appointment.status,
                                'Patient Type': 'Returning' if patient.is_returning else 'New',
                                'Form Sent': 'Yes' if appointment.form_sent else 'No'
                            })
                    
                    df_appointments = pd.DataFrame(appointments_data)
                    df_appointments.to_excel(writer, sheet_name='Appointments', index=False)
                
                # Sheet 2: Patient Summary
                patients = patient_db.get_all_patients()
                if patients:
                    patients_data = [patient.to_dict() for patient in patients]
                    df_patients = pd.DataFrame(patients_data)
                    df_patients.to_excel(writer, sheet_name='Patients', index=False)
                
                # Sheet 3: Statistics Summary
                total_patients = len(patients) if patients else 0
                total_appointments = len(appointments) if appointments else 0
                new_patients = len([p for p in patients if not p.is_returning]) if patients else 0
                
                stats_data = [{
                    'Metric': 'Total Patients',
                    'Value': total_patients
                }, {
                    'Metric': 'Total Appointments',
                    'Value': total_appointments
                }, {
                    'Metric': 'New Patients',
                    'Value': new_patients
                }, {
                    'Metric': 'Returning Patients',
                    'Value': total_patients - new_patients
                }, {
                    'Metric': 'Report Generated',
                    'Value': datetime.now().isoformat()
                }]
                
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='Statistics', index=False)
            
            logger.info(f"Exported comprehensive report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting comprehensive report: {e}")
            return ""

    def get_export_files(self) -> List[Dict]:
        """Get list of available export files"""
        try:
            files = []
            if os.path.exists(self.export_dir):
                for filename in os.listdir(self.export_dir):
                    if filename.endswith('.xlsx'):
                        filepath = os.path.join(self.export_dir, filename)
                        stat = os.stat(filepath)
                        
                        files.append({
                            'filename': filename,
                            'filepath': filepath,
                            'size_bytes': stat.st_size,
                            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x['modified'], reverse=True)
            return files
            
        except Exception as e:
            logger.error(f"Error getting export files: {e}")
            return []

# Global instance
export_service = ExportService()