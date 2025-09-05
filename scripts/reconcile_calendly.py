# scripts/reconcile_calendly.py
"""
Reconcile a Calendly scheduled event to a local appointment_id.
Usage:
  python -m scripts.reconcile_calendly --appointment_id A2463e920 --timeout 180
  python -m scripts.reconcile_calendly --email navya.bhalla1@example.com
"""
import os
import argparse
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv
from backend.calendly_client import poll_for_scheduled_event_by_appointment

load_dotenv()

DBPATH = os.path.join("data", "appointments.db")
CALENDAR_EVENTS_XLSX = os.path.join("data", "calendar_events.xlsx")
PAT = os.environ.get("CALENDLY_PAT")

def update_appointment_confirmed(appointment_id: str, scheduled_event: dict):
    conn = sqlite3.connect(DBPATH)
    cur = conn.cursor()
    uri = scheduled_event.get("uri") or scheduled_event.get("resource") or scheduled_event.get("id")
    now = datetime.utcnow().isoformat() + "Z"
    cur.execute("UPDATE appointments SET status=?, calendly_event_uri=?, updated_at=? WHERE appointment_id=?", ("confirmed", uri, now, appointment_id))
    conn.commit()
    conn.close()

def append_calendar_event_row_local(row: dict):
    # fallback append to calendar_events.xlsx using pandas
    try:
        import pandas as pd
    except Exception:
        raise RuntimeError("pandas required to append to calendar_events.xlsx")
    if os.path.exists(CALENDAR_EVENTS_XLSX):
        df = pd.read_excel(CALENDAR_EVENTS_XLSX, dtype=str)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_excel(CALENDAR_EVENTS_XLSX, index=False)

def append_calendar_event_row_try_scheduler_helper(row: dict):
    # Attempt to import the scheduler helper if present, else fallback
    try:
        from backend.scheduler import _append_calendar_event_row
        _append_calendar_event_row(row)
    except Exception:
        append_calendar_event_row_local(row)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--appointment_id", required=False)
    p.add_argument("--email", required=False)
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()
    if not args.appointment_id and not args.email:
        p.print_help()
        return

    appointment_id = args.appointment_id
    email = args.email

    print(f"Polling Calendly for appointment_id={appointment_id!r} email={email!r} (timeout {args.timeout}s)...")
    ev = poll_for_scheduled_event_by_appointment(appointment_id or "", invitee_email=email, pat=PAT, timeout_seconds=args.timeout, poll_interval=5)
    if not ev:
        print("No scheduled event found within timeout.")
        return

    # found scheduled event
    print("Found scheduled event (partial):", ev.get("uri") or ev.get("id"))
    matched_inv = ev.get("_matched_invitee", {})
    # Try to extract appointment_id from matched_inv answers if not supplied
    appt_id = appointment_id
    if not appt_id and matched_inv:
        qas = matched_inv.get("questions_and_answers") or matched_inv.get("answers") or []
        for q in qas:
            a = q.get("answer") or q.get("value") or ""
            if isinstance(a, str) and "appointment_id:" in a:
                appt_id = a.split("appointment_id:")[-1].strip()
                break
    if not appt_id:
        print("Could not determine appointment_id from scheduled event. Matched invitee payload (truncated):")
        print(json.dumps(matched_inv, indent=2)[:2000])
        return

    # Update appointment to confirmed in local DB
    update_appointment_confirmed(appt_id, ev)
    # Append calendar_events.xlsx row
    row = {
        "event_id": ev.get("id") or ev.get("uri") or "",
        "appointment_id": appt_id,
        "doctor_sheet": "unknown",  # best-effort
        "start_time": ev.get("start_time") or ev.get("start") or "",
        "end_time": ev.get("end_time") or ev.get("end") or "",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "source": "calendly"
    }
    append_calendar_event_row_try_scheduler_helper(row)
    print(f"Appointment {appt_id} marked confirmed and calendar_events.xlsx appended.")

if __name__ == "__main__":
    main()
