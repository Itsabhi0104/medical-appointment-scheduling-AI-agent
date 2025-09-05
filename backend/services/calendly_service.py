import os
import json
import requests
import pandas as pd
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)

class CalendlyService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.api_key = os.getenv("CALENDLY_PAT")
        self.base_url = "https://api.calendly.com"
        self.calendar_excel = os.path.join(data_dir, "calendar_events.xlsx")
        self.doctor_schedules = os.path.join(data_dir, "doctor_schedules.xlsx")
        
        # Doctor to Calendly mapping
        self.doctor_calendly_mapping = {
            "Dr Asha Rao": "asha-rao",
            "Dr Meera Iyer": "meera-iyer", 
            "Dr Vikram Gupta": "vikram-gupta",
            "Dr Vikram": "vikram-gupta"
        }
        
        os.makedirs(data_dir, exist_ok=True)
        self._ensure_calendar_excel()

    def _ensure_calendar_excel(self):
        """Create calendar_events.xlsx if it doesn't exist"""
        if not os.path.exists(self.calendar_excel):
            df = pd.DataFrame(columns=[
                "event_id", "appointment_id", "doctor_sheet", "patient_name",
                "start_time", "end_time", "duration_minutes", "status",
                "calendly_url", "created_at", "updated_at"
            ])
            df.to_excel(self.calendar_excel, index=False)

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers"""
        if not self.api_key:
            raise ValueError("CALENDLY_PAT not configured")
        
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_user_info(self) -> Optional[Dict]:
        """Get current user information"""
        try:
            response = requests.get(
                f"{self.base_url}/users/me",
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("resource", {})
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def list_event_types(self, user_uri: Optional[str] = None) -> List[Dict]:
        """List available event types"""
        try:
            if not user_uri:
                user_info = self.get_user_info()
                if not user_info:
                    return []
                user_uri = user_info.get("uri")

            response = requests.get(
                f"{self.base_url}/event_types",
                headers=self._get_headers(),
                params={"user": user_uri, "count": 100},
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("collection", [])
        except Exception as e:
            logger.error(f"Error listing event types: {e}")
            return []

    def create_booking_url(self, doctor_name: str, patient_data: Dict, 
                          appointment_data: Dict) -> str:
        """Create Calendly booking URL with prefilled data"""
        try:
            # Get doctor's Calendly slug
            doctor_slug = self.doctor_calendly_mapping.get(doctor_name, "default")
            
            # Base URL (you'll need to replace with actual Calendly URLs)
            base_url = f"https://calendly.com/your-clinic/{doctor_slug}"
            
            # Prepare prefill parameters
            params = {}
            
            if patient_data.get("first_name") and patient_data.get("last_name"):
                params["name"] = f"{patient_data['first_name']} {patient_data['last_name']}"
            
            if patient_data.get("email"):
                params["email"] = patient_data["email"]
            
            if appointment_data.get("start_time"):
                # Extract date for prefill
                start_dt = pd.to_datetime(appointment_data["start_time"])
                params["date"] = start_dt.strftime("%Y-%m-%d")
            
            # Add appointment ID as custom answer
            if appointment_data.get("appointment_id"):
                params["a1"] = f"appointment_id:{appointment_data['appointment_id']}"
            
            # Add insurance info
            if patient_data.get("insurance"):
                params["a2"] = f"insurance:{patient_data['insurance']}"
            
            if patient_data.get("member_id"):
                params["a3"] = f"member_id:{patient_data['member_id']}"
            
            # Build final URL
            if params:
                url = f"{base_url}?{urlencode(params)}"
            else:
                url = base_url
            
            logger.info(f"Created Calendly URL: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Error creating booking URL: {e}")
            return f"https://calendly.com/your-clinic/{doctor_slug}"

    def simulate_calendar_booking(self, appointment_data: Dict, patient_data: Dict) -> Dict:
        """Simulate calendar booking by updating Excel file"""
        try:
            # Load existing calendar events
            df = pd.read_excel(self.calendar_excel)
            
            # Create new event record
            event_record = {
                "event_id": f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "appointment_id": appointment_data.get("appointment_id", ""),
                "doctor_sheet": appointment_data.get("doctor", ""),
                "patient_name": f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip(),
                "start_time": appointment_data.get("start_time", ""),
                "end_time": appointment_data.get("end_time", ""),
                "duration_minutes": appointment_data.get("duration_minutes", 60),
                "status": "scheduled",
                "calendly_url": self.create_booking_url(
                    appointment_data.get("doctor", ""), 
                    patient_data, 
                    appointment_data
                ),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Add to DataFrame
            df = pd.concat([df, pd.DataFrame([event_record])], ignore_index=True)
            df.to_excel(self.calendar_excel, index=False)
            
            logger.info(f"Simulated calendar booking: {event_record['event_id']}")
            return {
                "success": True,
                "event_id": event_record["event_id"],
                "calendly_url": event_record["calendly_url"],
                "message": "Calendar booking simulated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error simulating calendar booking: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to simulate calendar booking"
            }

    def check_availability(self, doctor: str, date_str: str, 
                          duration_minutes: int = 60) -> List[Dict]:
        """Check doctor availability for a given date"""
        try:
            # Load doctor schedules
            if not os.path.exists(self.doctor_schedules):
                return []
            
            # Read doctor's schedule
            schedule_df = pd.read_excel(self.doctor_schedules, sheet_name=doctor)
            
            # Filter by date
            target_date = pd.to_datetime(date_str).date()
            schedule_df['date'] = pd.to_datetime(schedule_df['date']).dt.date
            day_schedule = schedule_df[schedule_df['date'] == target_date]
            
            if day_schedule.empty:
                return []
            
            # Load existing bookings
            calendar_df = pd.read_excel(self.calendar_excel)
            booked_slots = calendar_df[
                (calendar_df['doctor_sheet'] == doctor) & 
                (pd.to_datetime(calendar_df['start_time']).dt.date == target_date)
            ]
            
            available_slots = []
            
            for _, schedule in day_schedule.iterrows():
                start_time = pd.to_datetime(f"{target_date} {schedule['start_time']}")
                end_time = pd.to_datetime(f"{target_date} {schedule['end_time']}")
                slot_duration = int(schedule.get('slot_duration_default', 30))
                
                # Generate time slots
                current_time = start_time
                while current_time + timedelta(minutes=duration_minutes) <= end_time:
                    slot_end = current_time + timedelta(minutes=duration_minutes)
                    
                    # Check if slot is available
                    is_available = True
                    for _, booking in booked_slots.iterrows():
                        booking_start = pd.to_datetime(booking['start_time'])
                        booking_end = pd.to_datetime(booking['end_time'])
                        
                        # Check for overlap
                        if not (slot_end <= booking_start or current_time >= booking_end):
                            is_available = False
                            break
                    
                    if is_available:
                        available_slots.append({
                            "start_time": current_time.isoformat(),
                            "end_time": slot_end.isoformat(),
                            "duration_minutes": duration_minutes,
                            "doctor": doctor
                        })
                    
                    current_time += timedelta(minutes=slot_duration)
            
            return available_slots[:10]  # Return max 10 slots
            
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return []

    def get_scheduled_events(self, doctor: Optional[str] = None, 
                           days_ahead: int = 30) -> List[Dict]:
        """Get scheduled events from calendar Excel"""
        try:
            df = pd.read_excel(self.calendar_excel)
            
            # Filter by date range
            cutoff_date = datetime.now() + timedelta(days=days_ahead)
            df = df[pd.to_datetime(df['start_time']) <= cutoff_date]
            
            # Filter by doctor if specified
            if doctor:
                df = df[df['doctor_sheet'] == doctor]
            
            # Sort by start time
            df = df.sort_values('start_time')
            
            return df.to_dict(orient='records')
            
        except Exception as e:
            logger.error(f"Error getting scheduled events: {e}")
            return []

    def cancel_booking(self, event_id: str) -> Dict:
        """Cancel a booking (simulation)"""
        try:
            df = pd.read_excel(self.calendar_excel)
            
            if event_id in df['event_id'].values:
                df.loc[df['event_id'] == event_id, 'status'] = 'cancelled'
                df.loc[df['event_id'] == event_id, 'updated_at'] = datetime.now().isoformat()
                df.to_excel(self.calendar_excel, index=False)
                
                return {
                    "success": True,
                    "message": f"Event {event_id} cancelled successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Event {event_id} not found"
                }
                
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to cancel booking"
            }

    def get_calendar_stats(self) -> Dict:
        """Get calendar statistics"""
        try:
            df = pd.read_excel(self.calendar_excel)
            
            if df.empty:
                return {"total_events": 0}
            
            # Calculate stats
            total_events = len(df)
            scheduled_events = len(df[df['status'] == 'scheduled'])
            cancelled_events = len(df[df['status'] == 'cancelled'])
            
            # Events by doctor
            doctor_stats = df['doctor_sheet'].value_counts().to_dict()
            
            # Upcoming events (next 7 days)
            upcoming = df[
                (pd.to_datetime(df['start_time']) >= datetime.now()) &
                (pd.to_datetime(df['start_time']) <= datetime.now() + timedelta(days=7))
            ]
            upcoming_count = len(upcoming)
            
            return {
                "total_events": total_events,
                "scheduled_events": scheduled_events,
                "cancelled_events": cancelled_events,
                "upcoming_events": upcoming_count,
                "events_by_doctor": doctor_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting calendar stats: {e}")
            return {}

    def export_calendar_excel(self, filename: Optional[str] = None) -> str:
        """Export calendar to Excel file"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"calendar_export_{timestamp}.xlsx"
            
            export_path = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)
            
            # Load and format calendar data
            df = pd.read_excel(self.calendar_excel)
            
            # Add additional columns for export
            df['export_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Save to exports directory
            df.to_excel(export_path, index=False)
            
            logger.info(f"Calendar exported to: {export_path}")
            return export_path
            
        except Exception as e:
            logger.error(f"Error exporting calendar: {e}")
            raise

# Global instance
calendly_service = CalendlyService()