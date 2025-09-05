# scripts/verify_phase2.py
from backend import db as dbmod
from backend import scheduler as sched
from scripts.ensure_appointments_table import ensure as ensure_appt_schema
from datetime import datetime, timezone, timedelta

ensure_appt_schema()

def run():
    print()
    # 1) existing patient
    print("Querying existing patient by name and dob: Navya Bhalla 1943-05-28")
    p = dbmod.find_patient_by_name_dob("Navya", "Bhalla", "1943-05-28")
    if p:
        print(f" -> FOUND patient_id: {p['patient_id']} is_returning: {p.get('is_returning')}")
    else:
        print(" -> NOT FOUND")

    # 2) create a new patient
    print()
    print("Querying non-existing patient: Trial User9626, DOB=1999-01-01")
    p2 = dbmod.find_patient_by_name_dob("Trial", "User9626", "1999-01-01")
    if p2:
        print(" -> Unexpectedly found existing patient:", p2["patient_id"])
    else:
        print(" -> NOT FOUND, creating new patient...")
        new = dbmod.create_patient({"first_name":"Trial","last_name":"User9626","dob":"1999-01-01","phone":"","email":""})
        print(" -> Created new patient_id:", new["patient_id"])

    # 3) find available slots and book one
    doctor = "Dr Asha Rao"
    print()
    print("Using doctor sheet:", doctor)
    # choose a date from doctor schedules; for test choose first available from your scheduler:
    now = datetime.now(timezone.utc).astimezone()  # local tz + offset
    date0 = (now + timedelta(days=1)).date().isoformat()
    # call find_available_slots for a 60-minute appointment
    slots = sched.find_available_slots(doctor, date_from=date0, date_to=date0, duration_minutes=60, step_minutes=30, max_results=10)
    print(f"Found {len(slots)} available slots (showing up to 10):")
    for s in slots[:10]:
        print(" ", s.isoformat())

    if slots:
        chosen = slots[0].isoformat()
        print()
        print(f"Attempting to book slot {chosen} for patient P0001 (duration=60)...")
        res = sched.book_slot("P0001", doctor, chosen, duration_minutes=60, status="tentative", calendly_prefill_url=None)
        print(" ->", res)

        print()
        print("Attempting to book SAME slot for a different patient to check conflict...")
        res2 = sched.book_slot("P0051", doctor, chosen, duration_minutes=60)
        print(" ->", res2)

    # final counts:
    conn = sched.sqlite3.connect(sched.DB)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM appointments")
    cnt = cur.fetchone()[0]
    print()
    print("Appointments table now contains:", cnt, "row(s)")
    conn.close()

if __name__ == "__main__":
    run()
