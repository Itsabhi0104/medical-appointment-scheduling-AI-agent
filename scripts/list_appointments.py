import sqlite3
from pathlib import Path
db=Path("data/appointments.db")
conn=sqlite3.connect(db)
cur=conn.cursor()
cur.execute("SELECT appointment_id,patient_id,doctor_sheet,start_time,end_time,duration_minutes,status,created_at FROM appointments ORDER BY created_at DESC")
for row in cur.fetchall():
    print(dict(zip(["appointment_id","patient_id","doctor_sheet","start_time","end_time","duration_minutes","status","created_at"], row)))
conn.close()