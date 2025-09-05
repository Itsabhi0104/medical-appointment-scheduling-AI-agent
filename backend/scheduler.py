from __future__ import annotations
import os
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from dateutil import parser
import pandas as pd
import sqlite3
from filelock import FileLock

# Local project paths
DATA_DIR = os.path.join("data")
DOCTOR_SCHEDULES_XLSX = os.path.join(DATA_DIR, "doctor_schedules.xlsx")
CAL_EVENTS = os.path.join(DATA_DIR, "calendar_events.xlsx")
APPOINTMENTS_DB = os.path.join(DATA_DIR, "appointments.db")
DB = APPOINTMENTS_DB
LOCKFILE = os.path.join(DATA_DIR, "appointments.lock")

# fallback timezone from env
DEFAULT_TZ = os.environ.get("TZ", "Asia/Kolkata")


# helper: parse time strings like '09:00' to time object
def _parse_clock(tstr: str) -> time:
    tstr = str(tstr).strip()
    if not tstr:
        raise ValueError("empty time string")
    # accept HH:MM or HH:MM:SS
    return datetime.strptime(tstr, "%H:%M").time() if len(tstr.split(":")) == 2 else datetime.strptime(tstr, "%H:%M:%S").time()


def _to_zone_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
    return dt.astimezone(ZoneInfo(DEFAULT_TZ))


def _iso_to_dt(iso: str) -> datetime:
    return parser.isoparse(iso)


def _dt_to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
    return dt.isoformat()


def _overlaps(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    return (s1 < e2) and (e1 > s2)


# Load doctor schedule sheet as DataFrame
def load_doctor_schedule(sheet_name: str) -> pd.DataFrame:
    if not os.path.exists(DOCTOR_SCHEDULES_XLSX):
        raise FileNotFoundError(f"{DOCTOR_SCHEDULES_XLSX} not found")
    # Expect columns: date, start_time, end_time, slot_duration_default
    df = pd.read_excel(DOCTOR_SCHEDULES_XLSX, sheet_name=sheet_name, dtype=str)
    # normalize column names
    df.columns = [c.strip() for c in df.columns]
    return df.fillna("")


def _load_booked_intervals_for_doctor(doctor_sheet: str):
    """
    Return list of (start_dt, end_dt) for bookings for this doctor
    by consulting both appointments DB (confirmed/tentative) and calendar_events.xlsx.
    """
    intervals = []
    # from appointments DB
    if os.path.exists(APPOINTMENTS_DB):
        conn = sqlite3.connect(APPOINTMENTS_DB, timeout=30)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT start_time, end_time, status FROM appointments WHERE doctor_sheet = ? AND status IN ('tentative','confirmed')",
                (doctor_sheet,),
            )
            rows = cur.fetchall()
            for s, e, _ in rows:
                try:
                    si = parser.isoparse(str(s))
                    ei = parser.isoparse(str(e))
                    intervals.append((si, ei))
                except Exception:
                    continue
        finally:
            conn.close()
    # from calendar_events.xlsx (audit)
    if os.path.exists(CAL_EVENTS):
        try:
            df = pd.read_excel(CAL_EVENTS, dtype=str)
            df = df.fillna("")
            df = df[df["doctor_sheet"] == doctor_sheet]
            for _, r in df.iterrows():
                try:
                    s = parser.isoparse(str(r["start_time"]))
                    e = parser.isoparse(str(r["end_time"]))
                    intervals.append((s, e))
                except Exception:
                    continue
        except Exception:
            # if sheet corrupt or missing expected cols, ignore gracefully
            pass
    return intervals


def find_available_slots(
    doctor_sheet: str,
    date_from: str = None,
    date_to: str = None,
    duration_minutes: int = 30,
    step_minutes: int = None,
    max_results: int = 100,
):
    """
    Generate available start datetimes (timezone-aware) for `doctor_sheet` between date_from..date_to (YYYY-MM-DD).
    If date_from/date_to are None, generate for next 14 days (based on doctor_schedules.xlsx content).
    duration_minutes: length of appointment to check.
    step_minutes: granularity of candidate starts (if None, defaults to schedule slot_duration_default).
    Returns list of datetime objects (tz-aware).
    """
    tz = ZoneInfo(DEFAULT_TZ)
    df = load_doctor_schedule(doctor_sheet)
    # parse date range filter
    if date_from:
        date_from_dt = parser.isoparse(date_from).date()
    else:
        date_from_dt = None
    if date_to:
        date_to_dt = parser.isoparse(date_to).date()
    else:
        date_to_dt = None

    booked = _load_booked_intervals_for_doctor(doctor_sheet)

    candidates = []
    duration_td = timedelta(minutes=int(duration_minutes))

    # iterate schedule rows
    for _, row in df.iterrows():
        row_date = row.get("date") or row.get("Date") or row.get("day") or ""
        row_date = str(row_date).strip()
        if not row_date:
            continue
        try:
            day = parser.isoparse(row_date).date()
        except Exception:
            # ignore invalid date format
            continue
        if date_from_dt and day < date_from_dt:
            continue
        if date_to_dt and day > date_to_dt:
            continue

        start_time_s = row.get("start_time") or row.get("start") or row.get("Start") or ""
        end_time_s = row.get("end_time") or row.get("end") or row.get("End") or ""
        slot_default = int(row.get("slot_duration_default") or row.get("slot") or 30)

        try:
            start_clock = _parse_clock(start_time_s)
            end_clock = _parse_clock(end_time_s)
        except Exception:
            continue

        # combine to datetimes with tz
        day_start = datetime.combine(day, start_clock).replace(tzinfo=tz)
        day_end = datetime.combine(day, end_clock).replace(tzinfo=tz)
        if day_end <= day_start:
            # skip invalid
            continue

        step = int(step_minutes) if step_minutes else int(slot_default)

        # candidate generation: minute-level increments by step
        cur = day_start
        last_start_allowed = day_end - duration_td
        while cur <= last_start_allowed and len(candidates) < max_results:
            candidate_start = cur
            candidate_end = candidate_start + duration_td
            # skip if candidate in past
            if candidate_end <= datetime.now(tz):
                cur += timedelta(minutes=step)
                continue
            # check against booked intervals
            conflict = False
            for b_s, b_e in booked:
                # ensure b_s and b_e are tz-aware; coerce if needed
                if b_s.tzinfo is None:
                    b_s = b_s.replace(tzinfo=tz)
                if b_e.tzinfo is None:
                    b_e = b_e.replace(tzinfo=tz)
                if _overlaps(candidate_start, candidate_end, b_s, b_e):
                    conflict = True
                    break
            if not conflict:
                candidates.append(candidate_start)
            cur += timedelta(minutes=step)

    # sort and return
    candidates_sorted = sorted(candidates)
    return candidates_sorted[:max_results]


# --- Booking function ---
def _append_calendar_event_row(row: dict):
    # append audit row to data/calendar_events.xlsx (using pd.concat)
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(CAL_EVENTS):
        df = pd.read_excel(CAL_EVENTS, dtype=str).fillna("")
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_excel(CAL_EVENTS, index=False)


def _load_existing_intervals_from_db(doctor_sheet: str):
    """Return list of (start_dt, end_dt) from appointments DB for given doctor."""
    intervals = []
    if not os.path.exists(APPOINTMENTS_DB):
        return intervals
    conn = sqlite3.connect(APPOINTMENTS_DB, timeout=30)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT start_time, end_time, status FROM appointments WHERE doctor_sheet = ? AND status IN ('tentative','confirmed')",
            (doctor_sheet,),
        )
        rows = cur.fetchall()
        for s, e, _ in rows:
            try:
                si = parser.isoparse(str(s))
                ei = parser.isoparse(str(e))
                intervals.append((si, ei))
            except Exception:
                continue
    finally:
        conn.close()
    return intervals


def book_slot(patient_id: str, doctor_sheet: str, start_iso: str, duration_minutes: int = 30, status: str = "tentative", calendly_prefill_url: str = None):
    """
    Attempt to book a slot. Returns dict with keys:
      success (bool), appointment_id (or None), status, message, calendly_prefill_url (if provided)
    Booking is atomic under a file lock.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    # ensure appointments table exists (idempotent)
    try:
        # import here to avoid circular imports; scripts.ensure_appointments_table should exist
        from scripts.ensure_appointments_table import ensure as ensure_appt_schema

        ensure_appt_schema()
    except Exception:
        # if missing, proceed (caller likely created earlier) - we want to fail later if DB missing
        pass

    lock = FileLock(LOCKFILE, timeout=30)
    with lock:
        # parse start and end
        try:
            start_dt = parser.isoparse(start_iso)
        except Exception:
            # try to parse naive date/time and attach default tz
            start_dt = parser.parse(start_iso)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
        end_dt = start_dt + timedelta(minutes=int(duration_minutes))

        # check against existing appointments (python-side checking)
        existing = _load_existing_intervals_from_db(doctor_sheet)
        for s, e in existing:
            if s.tzinfo is None:
                s = s.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
            if e.tzinfo is None:
                e = e.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
            if _overlaps(start_dt, end_dt, s, e):
                return {"success": False, "appointment_id": None, "message": "Slot not available or outside doctor's schedule"}

        # also check calendar events audit (safety)
        cal_booked = _load_booked_intervals_for_doctor(doctor_sheet)
        for s, e in cal_booked:
            if s.tzinfo is None:
                s = s.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
            if e.tzinfo is None:
                e = e.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
            if _overlaps(start_dt, end_dt, s, e):
                return {"success": False, "appointment_id": None, "message": "Slot conflicts with calendar events (already booked)"}

        # safe insert into sqlite
        conn = sqlite3.connect(APPOINTMENTS_DB, timeout=30)
        cur = conn.cursor()
        appt_id = "A" + uuid.uuid4().hex[:8]
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        try:
            cur.execute(
                "INSERT INTO appointments (appointment_id, patient_id, doctor_sheet, start_time, end_time, duration_minutes, status, created_at, updated_at, form_sent, calendly_event_uri) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    appt_id,
                    patient_id,
                    doctor_sheet,
                    start_dt.isoformat(),
                    end_dt.isoformat(),
                    int(duration_minutes),
                    status,
                    now_iso,
                    now_iso,
                    0,
                    calendly_prefill_url or "",
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return {"success": False, "appointment_id": None, "message": f"DB integrity error: {e}"}
        finally:
            conn.close()

        # append to calendar_events.xlsx (audit / calendar simulation)
        row = {
            "event_id": "",  # populate when reconciled with Calendly
            "appointment_id": appt_id,
            "doctor_sheet": doctor_sheet,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "created_at": now_iso,
            "source": "local" if status == "tentative" else "confirmed",
        }
        try:
            _append_calendar_event_row(row)
        except Exception:
            # don't die if excel write fails; appointment is still inserted
            pass

        # return success
        return {"success": True, "appointment_id": appt_id, "status": status, "calendly_prefill_url": calendly_prefill_url or ""}

