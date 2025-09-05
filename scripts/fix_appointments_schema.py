# scripts/fix_appointments_schema.py
"""
Safe migration helper for appointments DB.
Adds missing columns (updated_at, form_sent, calendly_event_uri) if they do not exist.
Usage:
  python -m scripts.fix_appointments_schema
"""

import sqlite3, os

DBPATH = os.path.join("data", "appointments.db")

def get_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    # returns list of column names
    return [r[1] for r in rows]

def add_column(conn, table, col_def):
    cur = conn.cursor()
    print(f"Adding column: {col_def} to table {table} ...")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    conn.commit()

def main():
    if not os.path.exists(DBPATH):
        print("Database not found at", DBPATH)
        return
    conn = sqlite3.connect(DBPATH)
    cols = get_columns(conn, "appointments")
    print("appointments columns currently:", cols)

    needed = {
        "updated_at": "updated_at TEXT",
        "form_sent": "form_sent INTEGER DEFAULT 0",
        "calendly_event_uri": "calendly_event_uri TEXT"
    }

    for name, definition in needed.items():
        if name not in cols:
            try:
                add_column(conn, "appointments", definition)
                print(f"-> Added column '{name}'.")
            except Exception as e:
                print(f"Failed to add column {name}: {e}")
        else:
            print(f"-> Column '{name}' already present.")
    # print final columns
    cols2 = get_columns(conn, "appointments")
    print("Final appointments columns:", cols2)
    conn.close()

if __name__ == "__main__":
    main()
