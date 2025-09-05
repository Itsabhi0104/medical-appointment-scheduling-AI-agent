import sqlite3
from pathlib import Path
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    from backports.zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB = DATA_DIR / "appointments.db"
LOCAL_TZ = ZoneInfo("Asia/Kolkata")

def _parse_and_ensure_iso(s):
    """
    Parse stored string s, coerce to LOCAL_TZ if naive, and return isoformat with offset.
    """
    if s is None:
        return None
    s = s.strip()
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # try fallback patterns
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            raise ValueError(f"Unrecognized datetime format: {s}")
    # If naive, assume local tz
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.isoformat()

def migrate():
    if not DB.exists():
        print("No appointments.db found at", DB)
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT appointment_id, start_time, end_time FROM appointments")
    rows = cur.fetchall()
    updated = 0
    for appt_id, s, e in rows:
        try:
            new_s = _parse_and_ensure_iso(s) if s else None
            new_e = _parse_and_ensure_iso(e) if e else None
        except Exception as ex:
            print("Skipping", appt_id, "due to parse error:", ex)
            continue
        # update only if different
        if new_s and new_e:
            cur.execute("UPDATE appointments SET start_time=?, end_time=? WHERE appointment_id=?", (new_s, new_e, appt_id))
            updated += 1
    conn.commit()
    conn.close()
    print(f"Migration complete. Updated {updated} rows (if any).")

if __name__ == "__main__":
    migrate()