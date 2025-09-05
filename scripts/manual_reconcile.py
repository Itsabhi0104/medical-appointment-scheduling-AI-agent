# scripts/manual_reconcile.py
import sqlite3, os
from datetime import datetime, timezone
import pandas as pd

DB = os.path.join("data","appointments.db")
CAL_EVENTS = os.path.join("data","calendar_events.xlsx")

def mark_confirmed(appointment_id, start_iso, end_iso, calendly_event_uri=None):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # use timezone-aware UTC time to avoid DeprecationWarning
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur.execute("UPDATE appointments SET status=?, calendly_event_uri=?, updated_at=? WHERE appointment_id=?", ("confirmed", calendly_event_uri or "", now, appointment_id))
        conn.commit()
    except sqlite3.OperationalError as e:
        # likely missing column updated_at — fallback to update without updated_at
        print("UPDATE with updated_at failed, retrying without updated_at. Reason:", e)
        cur.execute("UPDATE appointments SET status=?, calendly_event_uri=? WHERE appointment_id=?", ("confirmed", calendly_event_uri or "", appointment_id))
        conn.commit()
    conn.close()

    # append to calendar_events.xlsx
    row = {
        "event_id": calendly_event_uri or "",
        "appointment_id": appointment_id,
        "doctor_sheet": "",
        "start_time": start_iso,
        "end_time": end_iso,
        "created_at": now,
        "source": "manual"
    }
    if os.path.exists(CAL_EVENTS):
        df = pd.read_excel(CAL_EVENTS, dtype=str)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_excel(CAL_EVENTS, index=False)
    print("Marked confirmed and appended calendar_events.xlsx row for", appointment_id)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--appointment_id", required=True)
    p.add_argument("--start", required=True, help="ISO start like 2025-09-18T10:00:00+05:30")
    p.add_argument("--end", required=True, help="ISO end like 2025-09-18T10:30:00+05:30")
    p.add_argument("--calendly_uri", required=False)
    args = p.parse_args()
    mark_confirmed(args.appointment_id, args.start, args.end, args.calendly_uri)
