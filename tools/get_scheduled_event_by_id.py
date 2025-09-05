# tools/get_scheduled_event_by_id.py
import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv()
PAT = os.environ.get("CALENDLY_PAT")
if not PAT:
    raise SystemExit("Set CALENDLY_PAT in .env")

if len(sys.argv) < 2:
    print("Usage: python tools/get_scheduled_event_by_id.py <scheduled_event_id_or_uri>")
    print("Examples: python tools/get_scheduled_event_by_id.py https://calendly.com/app/scheduled_events/user/46051781")
    sys.exit(1)

arg = sys.argv[1]
# Accept either an ID or a full uri
if arg.startswith("http"):
    # try to extract the id at the end
    if "scheduled_events" in arg:
        se_id = arg.rstrip("/").split("/")[-1]
    else:
        se_id = arg
else:
    se_id = arg

headers = {"Authorization": f"Bearer {PAT}", "Accept": "application/json"}
url = f"https://api.calendly.com/scheduled_events/{se_id}"
r = requests.get(url, headers=headers, timeout=20)
print("HTTP", r.status_code)
if r.status_code != 200:
    print("Response text (truncated):", r.text[:1000])
    r.raise_for_status()
js = r.json()
print(json.dumps(js, indent=2))
# Print invitees for easy inspection
invitees_url = f"https://api.calendly.com/scheduled_events/{se_id}/invitees"
ri = requests.get(invitees_url, headers=headers, timeout=20)
print("Invitees HTTP:", ri.status_code)
print(json.dumps(ri.json(), indent=2)[:4000])
