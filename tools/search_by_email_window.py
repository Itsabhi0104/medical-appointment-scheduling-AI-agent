# tools/search_by_email_window.py
import os, requests, json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from urllib.parse import urljoin

load_dotenv()
PAT = os.environ.get("CALENDLY_PAT")
if not PAT:
    raise SystemExit("Set CALENDLY_PAT in .env")

HEADERS = {"Authorization": f"Bearer {PAT}", "Accept": "application/json"}
BASE = "https://api.calendly.com"

def list_scheduled(params):
    r = requests.get(urljoin(BASE, "scheduled_events"), headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def fetch_invitees(scheduled_event_id):
    r = requests.get(urljoin(BASE, f"scheduled_events/{scheduled_event_id}/invitees"), headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

email = input("Invitee email to search for (e.g. navya.bhalla1@example.com): ").strip()
date_from = input("Start date (YYYY-MM-DD) (e.g. 2025-08-25): ").strip()
date_to = input("End date (YYYY-MM-DD) (e.g. 2025-09-30): ").strip()

params = {"count": 100, "min_start_time": date_from + "T00:00:00Z", "max_start_time": date_to + "T23:59:59Z"}
print("Searching scheduled events between", params["min_start_time"], "and", params["max_start_time"])
js = list_scheduled(params)
found = False
for ev in js.get("collection", []):
    ev_id = ev.get("id")
    st = ev.get("start_time") or ev.get("start")
    print("Event:", ev_id, st, ev.get("uri"))
    invjs = fetch_invitees(ev_id)
    for inv in invjs.get("collection", []):
        if (inv.get("email") or "").lower() == email.lower():
            print("  Found invitee match:", inv.get("name"), inv.get("email"))
            print("  QA:", json.dumps(inv.get("questions_and_answers") or inv.get("answers") or [], indent=2))
            found = True
if not found:
    print("No events found for that email in the window.")
