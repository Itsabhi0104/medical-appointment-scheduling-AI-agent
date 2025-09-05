# backend/notifications.py
import os
import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "notifications.log")

# Path to the intake form (use the PDF you uploaded)
INTAKE_FORM_PATH = os.path.join("forms", "New Patient Intake Form.pdf")

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(INTAKE_FORM_PATH), exist_ok=True)

def log_notification(message: str):
    """Append a notification message to logs/notifications.log with timestamp."""
    ts = datetime.datetime.now().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")
    print(f"[NOTIFY] {message}")  # also echo to console for demo


def send_confirmation(appointment: dict, contact_method: str = "none", recipient: str = None):
    """
    Log a booking confirmation and attach/send intake form if confirmed.
    contact_method: "email", "phone", or "none"
    """
    doctor = appointment.get("doctor")
    start_time = appointment.get("start")
    appt_id = appointment.get("appointment_id")

    msg = f"Appointment confirmed: {doctor} on {start_time} — ID {appt_id}"
    log_notification(msg)

    # Handle contact preference
    if contact_method == "email" and recipient:
        log_notification(f"📧 Confirmation email would be sent to {recipient}.")
    elif contact_method == "phone" and recipient:
        log_notification(f"📱 Confirmation SMS would be sent to {recipient}.")
    else:
        log_notification("ℹ️ Confirmation logged (no contact method selected).")

    # Attach intake form (only after confirmation)
    if os.path.exists(INTAKE_FORM_PATH):
        log_notification(
            f"📄 Intake form available for patient: {INTAKE_FORM_PATH}. "
            "Marking form_sent = False (not yet returned)."
        )
    else:
        log_notification("⚠️ Intake form file not found. Please upload it to /forms/ directory.")


def mark_form_sent(appointment_id: str):
    """
    Mark the intake form as sent in logs (for demo).
    In a real system, update DB/Excel export to set form_sent = Y.
    """
    log_notification(f"Form sent to patient for Appointment ID {appointment_id} (form_sent = Y).")
