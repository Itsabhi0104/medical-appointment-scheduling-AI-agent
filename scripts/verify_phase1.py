import pandas as pd
import json
from pathlib import Path
from datetime import datetime

def main():
    base = Path(__file__).resolve().parents[1]
    data_dir = base / "data"

    # Load patients.csv
    patients_path = data_dir / "patients.csv"
    patients = pd.read_csv(patients_path, dtype=str)
    print(f"Loaded patients.csv: {len(patients)} rows")

    # Show first sample row
    sample = patients.iloc[0].to_dict()
    if "is_returning" in sample and isinstance(sample["is_returning"], str):
        sample["is_returning"] = sample["is_returning"].lower() in ("true","1","t","yes")
    print("Sample row:", json.dumps(sample, ensure_ascii=False))

    # Load doctor schedules Excel
    schedules_path = data_dir / "doctor_schedules.xlsx"
    xlsx = pd.ExcelFile(schedules_path)
    sheets = xlsx.sheet_names
    print(f"doctor_schedules.xlsx: {len(sheets)} sheets found: {sheets}")

    # For first doctor sheet, compute total available slots
    first_doctor = None
    for sheet in sheets:
        if sheet.lower() not in ["doctors", "appointments_template"]:
            first_doctor = sheet
            break

    if first_doctor:
        df_doc = pd.read_excel(schedules_path, sheet_name=first_doctor, dtype=str)
        total_slots = 0
        for _, row in df_doc.iterrows():
            try:
                start = datetime.strptime(row["start_time"], "%H:%M")
                end = datetime.strptime(row["end_time"], "%H:%M")
                duration = int(row.get("slot_duration_default", 30))
                minutes = int((end - start).total_seconds() // 60)
                total_slots += minutes // duration
            except Exception:
                continue
        print(f"{first_doctor} available slots in next {len(df_doc)//2} days: {total_slots}")

if __name__ == "__main__":
    main()
