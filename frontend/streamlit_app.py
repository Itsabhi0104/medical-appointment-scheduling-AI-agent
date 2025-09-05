import os
import io
import uuid
from datetime import datetime
import streamlit as st
import pandas as pd

# ensure project root is importable
import sys
sys.path.append(os.path.abspath("."))

from backend.agents.flow import run_booking_flow
import backend.db as db
import backend.scheduler as scheduler
import backend.export as exporter
import backend.notifications as notifications
from scripts.ensure_appointments_table import ensure as ensure_appt_schema
ensure_appt_schema()

DATA_DIR = os.path.join(os.path.abspath("."), "data")
EXPORTS_DIR = os.path.join(os.path.abspath("."), "exports")
LOGS_DIR = os.path.join(os.path.abspath("."), "logs")
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

st.set_page_config(page_title="RagaAI — Scheduling Demo", layout="centered")

st.title("RagaAI — Medical Scheduling Demo")
st.markdown(
    "Type a short message (greeting + availability) and the agent will parse it, "
    "look up patient, show available slots, and allow you to confirm a booking."
)

if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "selected_slot" not in st.session_state:
    st.session_state.selected_slot = None
if "created_appointment" not in st.session_state:
    st.session_state.created_appointment = None

st.header("1) Greeting / Request")
utterance = st.text_area("User utterance (example):", value="Hi I'm Rajesh Kumar, DOB 1992-05-12. I want Dr Asha Rao next Tuesday morning for a fever. My email is rajesh.k@example.com", height=120)

cols = st.columns([1, 1, 1])
with cols[0]:
    if st.button("Parse & Suggest"):
        # run NLU + flow
        res = run_booking_flow(utterance)
        st.session_state.last_result = res
        st.session_state.selected_slot = None
        st.session_state.created_appointment = None

with cols[1]:
    if st.button("Clear"):
        st.session_state.last_result = None
        st.session_state.selected_slot = None
        st.session_state.created_appointment = None
        st.experimental_rerun()

st.markdown("---")

res = st.session_state.last_result
if not res:
    st.info("No parsed data yet. Click **Parse & Suggest** to continue.")
    st.stop()

parsed = res.get("parsed", {})
patient = res.get("patient")
suggestions = res.get("suggestions", [])

st.header("2) Parsed details / Patient lookup")
st.write("**Parsed output (from NLU):**")
st.json(parsed)

if patient:
    st.success(f"Found patient: {patient.get('first_name','')} {patient.get('last_name','')} (ID: {patient.get('patient_id')})")
    st.write(patient)
else:
    st.warning("No matching patient found (this will create a new patient on confirm).")

st.markdown("---")
st.header("3) Suggested slots")
if suggestions:
    st.write("Choose an available slot from these suggestions:")
    # show a table and selection
    df_s = pd.DataFrame(suggestions)
    df_s.index = df_s.index + 1
    st.dataframe(df_s.rename(columns={"doctor": "Doctor", "start": "Start (ISO)"}), height=200)
    options = [f"{row['doctor']}  —  {row['start']}" for row in suggestions]
    sel = st.radio("Select a slot", options)
    if sel:
        st.session_state.selected_slot = suggestions[options.index(sel)]
else:
    st.info("No slot suggestions were returned. Provide a date/time or broaden the range and try again.")

st.markdown("---")
st.header("4) Confirm booking")

contact_method = st.radio("Preferred contact method for confirmation/form:", ("email", "phone", "none"))
contact_value = None
if contact_method == "email":
    contact_value = st.text_input("Email to use (leave blank to use parsed email):", value=parsed.get("email") or "")
elif contact_method == "phone":
    contact_value = st.text_input("Phone to use (leave blank to use parsed phone):", value=parsed.get("phone") or "")

if st.session_state.selected_slot:
    st.write("Selected slot:")
    st.write(st.session_state.selected_slot)
    if st.button("Confirm booking"):
        # ensure patient exists or create
        p = patient
        if not p:
            # Create new patient (minimal fields)
            first = parsed.get("first_name") or parsed.get("name") or "New"
            last = parsed.get("last_name") or ""
            dob = parsed.get("dob") or None
            email = parsed.get("email") or (contact_value if contact_method == "email" else None)
            phone = parsed.get("phone") or (contact_value if contact_method == "phone" else None)
            new_p = db.create_patient(first_name=first, last_name=last, dob=dob, phone=phone, email=email)
            p = new_p

        # detect duration: returning = 30 else 60
        duration = 30 if p.get("is_returning") else 60
        doctor = st.session_state.selected_slot["doctor"]
        start_iso = st.session_state.selected_slot["start"]
        # try to use scheduler.book_slot if available
        booked = None
        try:
            booked = scheduler.book_slot(patient_id=p["patient_id"], doctor=doctor, start_time=start_iso, duration=duration)
        except Exception as e:
            # fallback: write appointment directly using exporter helper (simple insert)
            st.warning("scheduler.book_slot failed; using fallback DB write. See logs.")
            import sqlite3
            appt_id = "A" + uuid.uuid4().hex[:8]
            conn = sqlite3.connect(os.path.join(DATA_DIR, "appointments.db"))
            cur = conn.cursor()
            # attempt create table if not exists
            cur.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id TEXT PRIMARY KEY,
                patient_id TEXT,
                doctor_sheet TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                status TEXT,
                created_at TEXT,
                form_sent INTEGER DEFAULT 0
            )
            """)
            start_dt = pd.to_datetime(start_iso)
            end_dt = (start_dt + pd.Timedelta(minutes=duration)).isoformat()
            now = datetime.utcnow().isoformat()
            cur.execute("INSERT INTO appointments (appointment_id, patient_id, doctor_sheet, start_time, end_time, duration_minutes, status, created_at, form_sent) VALUES (?,?,?,?,?,?,?,?,?)",
                        (appt_id, p["patient_id"], doctor, start_iso, end_dt, duration, "confirmed", now, 0))
            conn.commit()
            conn.close()
            booked = {"success": True, "appointment_id": appt_id, "message": "Booked (fallback)"}

        if booked and booked.get("success"):
            appt_id = booked.get("appointment_id")
            st.success(f"Appointment confirmed: {doctor} on {start_iso} — Appointment ID: {appt_id}")
            notifications.notify(f"Appointment confirmed: {appt_id} patient={p['patient_id']} doctor={doctor} start={start_iso}")
            # create export
            export_path = exporter.export_bookings(export_dir=EXPORTS_DIR)
            # show download link
            with open(export_path, "rb") as fh:
                data = fh.read()
            st.markdown("---")
            st.download_button(label="Download admin export (Excel)", data=data, file_name=os.path.basename(export_path), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            # mark created appointment in session for debugging
            st.session_state.created_appointment = {"appointment_id": appt_id, "patient_id": p["patient_id"], "doctor": doctor, "start": start_iso}
        else:
            st.error(f"Failed to book: {booked}")
else:
    st.info("Select a suggestion to confirm a booking.")

st.markdown("---")
st.caption("Demo notes: this is a demo Streamlit app. The agent uses the backend NLU + scheduler to suggest slots and confirm bookings; exports are created in the project's `exports/` folder and notifications written to `logs/notifications.log`.")
