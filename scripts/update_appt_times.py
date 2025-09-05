# scripts/update_appt_times.py
import sqlite3, os
from datetime import datetime, timezone

DB = os.path.join("data","appointments.db")

def update_appt(appointment_id, new_start_iso, new_end_iso):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("UPDATE appointments SET start_time=?, end_time=?, status=?, updated_at=? WHERE appointment_id=?",
                (new_start_iso, new_end_iso, "confirmed", now, appointment_id))
    conn.commit()
    conn.close()
    print("Updated appointment", appointment_id, "to", new_start_iso, "-", new_end_iso)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python scripts/update_appt_times.py <APPT_ID> <START_ISO> <END_ISO>")
    else:
        update_appt(sys.argv[1], sys.argv[2], sys.argv[3])
