# backend/calendly_client.py
import os
import time
import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode, quote_plus

CALENDLY_API_BASE = "https://api.calendly.com"

def _headers(pat: Optional[str]):
    token = pat or os.environ.get("CALENDLY_PAT")
    if not token:
        raise RuntimeError("CALENDLY_PAT not set in env or passed to function")
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

def get_user_info(pat: Optional[str] = None) -> Dict[str, Any]:
    """Call users/me and return resource payload."""
    headers = _headers(pat)
    r = requests.get(f"{CALENDLY_API_BASE}/users/me", headers=headers, timeout=15)
    r.raise_for_status()
    return r.json().get("resource", r.json())

def list_event_types_for_user(user_uri: Optional[str] = None, pat: Optional[str] = None) -> List[Dict]:
    """Return list of event_types for the user (uses user_uri from users/me if not provided)."""
    headers = _headers(pat)
    if user_uri is None:
        user_uri = get_user_info(pat).get("uri")
    url = f"{CALENDLY_API_BASE}/event_types"
    params = {"user": user_uri, "per_page": 100}
    out = []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        js = r.json()
        out.extend(js.get("collection", []))
        url = js.get("next_page")
        params = {}
    return out

def build_prefill_url(event_type_url_or_slug: str, invitee_email: Optional[str]=None, invitee_name: Optional[str]=None, date_iso: Optional[str]=None, answers: Optional[Dict]=None) -> str:
    """
    Build Calendly prefill URL.
     - event_type_url_or_slug: either a full URL (https://calendly.com/user/slug) or 'user/slug'
     - date_iso: prefer YYYY-MM-DD or full ISO (we strip to date)
     - answers: dict of additional answer keys to pass as a1/a2...
    Returns a full URL string.
    """
    # normalize base
    base = event_type_url_or_slug
    if not base.startswith("http"):
        if base.startswith("calendly.com/"):
            base = "https://" + base
        else:
            base = "https://calendly.com/" + base

    params = {}
    if invitee_name:
        params["name"] = invitee_name
    if invitee_email:
        params["email"] = invitee_email
    if date_iso:
        params["date"] = date_iso.split("T")[0]
    if answers:
        for i, (k, v) in enumerate(answers.items(), start=1):
            params[f"a{i}"] = f"{k}:{v}"
    if params:
        return base + ("?" + urlencode(params, quote_via=quote_plus))
    return base

def list_scheduled_events_for_user(pat: Optional[str] = None, user_uri: Optional[str] = None, count: int = 100) -> List[Dict]:
    headers = _headers(pat)
    if user_uri is None:
        user_uri = get_user_info(pat).get("uri")
    params = {"user": user_uri, "count": count}
    r = requests.get(f"{CALENDLY_API_BASE}/scheduled_events", headers=headers, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("collection", [])

def _fetch_invitees_for_scheduled_event(scheduled_event_id: str, pat: Optional[str] = None) -> List[Dict]:
    headers = _headers(pat)
    url = f"{CALENDLY_API_BASE}/scheduled_events/{scheduled_event_id}/invitees"
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json().get("collection", [])

def find_scheduled_event_by_appointment_id(appointment_id: str, invitee_email: Optional[str] = None, pat: Optional[str] = None) -> Optional[Dict]:
    """
    Search scheduled events for invitee answers that include 'appointment_id:<value>'.
    Returns the scheduled_event dict with an added key '_matched_invitee' for the invitee that matched.
    """
    headers = _headers(pat)
    user = get_user_info(pat)
    user_uri = user.get("uri")
    url = f"{CALENDLY_API_BASE}/scheduled_events"
    params = {"user": user_uri, "count": 100}
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        js = r.json()
        coll = js.get("collection", [])
        for ev in coll:
            ev_id = ev.get("id")
            try:
                invitees = _fetch_invitees_for_scheduled_event(ev_id, pat=pat)
            except Exception:
                invitees = []
            for inv in invitees:
                inv_email = (inv.get("email") or "").lower()
                if invitee_email and invitee_email.lower() != inv_email:
                    continue
                # combine common fields and answers
                combined_texts = []
                # questions_and_answers may be list of {question, answer}
                for q in inv.get("questions_and_answers") or inv.get("answers") or []:
                    ans = q.get("answer") or q.get("value") or ""
                    combined_texts.append(str(ans))
                # also check name, location, text_reminder_number etc
                combined_texts.append(inv.get("name") or "")
                combined_texts.append(inv.get("email") or "")
                combined = " ".join(combined_texts)
                if appointment_id in combined:
                    ev_copy = ev.copy()
                    ev_copy["_matched_invitee"] = inv
                    return ev_copy
        url = js.get("next_page")
        params = {}
    return None

def poll_for_scheduled_event_by_appointment(appointment_id: str, invitee_email: Optional[str] = None, pat: Optional[str] = None, timeout_seconds: int = 120, poll_interval: int = 5) -> Optional[Dict]:
    """
    Poll up to timeout_seconds for any scheduled_event that contains appointment_id in invitee answers.
    Returns scheduled_event dict (with _matched_invitee) or None.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            ev = find_scheduled_event_by_appointment_id(appointment_id, invitee_email=invitee_email, pat=pat)
        except Exception:
            ev = None
        if ev:
            return ev
        time.sleep(poll_interval)
    return None
