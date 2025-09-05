# tools/calendly_list_events.py
import os, requests, json
from dotenv import load_dotenv

load_dotenv()
PAT = os.environ.get("CALENDLY_PAT")
if not PAT:
    raise SystemExit("Set CALENDLY_PAT in your environment or .env")

HEADERS = {"Authorization": f"Bearer {PAT}", "Accept": "application/json"}

def get_user():
    r = requests.get("https://api.calendly.com/users/me", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json().get("resource", r.json())

def list_event_types_for_user(user_uri):
    url = "https://api.calendly.com/event_types"
    params = {"user": user_uri, "per_page": 100}
    out = []
    while url:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        # If Calendly rejects without extra params it will be visible here
        r.raise_for_status()
        js = r.json()
        collection = js.get("collection", [])
        out.extend(collection)
        url = js.get("next_page")
        params = {}
    return out

if __name__ == "__main__":
    print("Using PAT from env. Getting user info...")
    user = get_user()
    print(json.dumps(user, indent=2))
    user_uri = user.get("uri")
    if not user_uri:
        raise SystemExit("Could not find user uri in users/me response")
    print("\nListing event types for user (name, slug, scheduling_url):\n")
    ets = list_event_types_for_user(user_uri)
    if not ets:
        print("No event types found for this user.")
    for et in ets:
        name = et.get("name")
        slug = et.get("slug")
        sched = et.get("scheduling_url") or et.get("uri") or et.get("resource")
        print(f"- name: {name!r}\n  slug: {slug!r}\n  scheduling_url: {sched!r}\n")
