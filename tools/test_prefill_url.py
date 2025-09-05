# tools/test_prefill_url.py
import os, requests
from dotenv import load_dotenv
from urllib.parse import urlencode, quote_plus

load_dotenv()
PAT = os.environ.get("CALENDLY_PAT")
BASE = os.environ.get("CALENDLY_EVENT_TYPE_UUID")  # should be scheduling_url or username/slug

if not BASE:
    raise SystemExit("Set CALENDLY_EVENT_TYPE_UUID in .env to the scheduling_url (or username/slug)")

def normalize_base(base):
    # If full URL already
    if base.startswith("http://") or base.startswith("https://"):
        return base
    # If starts with calendly.com/... or contains slash username/slug
    if base.startswith("calendly.com/"):
        return "https://" + base
    if "/" in base:
        # assume username/slug
        return "https://calendly.com/" + base
    # fallback: treat as slug only (unlikely)
    return "https://calendly.com/" + base

def build_prefill(base, name=None, email=None, date=None, answers=None):
    params = {}
    if name:
        params["name"] = name
    if email:
        params["email"] = email
    if date:
        params["date"] = date.split("T")[0]
    if answers:
        for i,(k,v) in enumerate(answers.items(), start=1):
            params[f"a{i}"] = f"{k}:{v}"
    return base + ("?" + urlencode(params, quote_via=quote_plus) if params else "")

base_norm = normalize_base(BASE)
prefill = build_prefill(base_norm, name="Navya Bhalla", email="navya.bhalla1@example.com", date="2025-09-04")
print("Prefill URL:", prefill)

try:
    r = requests.get(prefill, timeout=15, allow_redirects=True)
    print("HTTP status:", r.status_code)
    print("Final URL after redirects:", r.url)
    print("Response length (chars):", len(r.text))
    print("Response snippet (first 400 chars):")
    print(r.text[:400].replace("\n"," "))
except Exception as e:
    print("Request failed:", e)
