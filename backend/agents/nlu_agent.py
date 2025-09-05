from __future__ import annotations
import os
import re
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()  # ensure .env variables are loaded for this process

from pydantic import BaseModel, Field, validator
from dateutil import parser as dateparser

# LangChain LLM base class (used to create a LangChain-compatible wrapper)
try:
    from langchain.llms.base import LLM
except Exception:
    # fallback: define a minimal base if not present (keeps compatibility)
    class LLM:
        def __init__(self, **kwargs): pass

# Attempt to import google.generativeai (Gemini client)
try:
    import google.generativeai as genai
except Exception:
    genai = None

# Logging setup
LOG_DIR = os.path.join("logs")
os.makedirs(LOG_DIR, exist_ok=True)
PARSES_LOG = os.path.join(LOG_DIR, "parses.log")
RAW_LLM_LOG = os.path.join(LOG_DIR, "raw_llm.log")

parse_logger = logging.getLogger("nlu_parses")
if not parse_logger.handlers:
    fh = logging.FileHandler(PARSES_LOG, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(message)s"))
    parse_logger.addHandler(fh)
    parse_logger.setLevel(logging.INFO)


# ---------------- Pydantic schema ----------------
class PreferredTimeWindow(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class ParseResult(BaseModel):
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source: str = Field("heuristic")  # "llm" or "heuristic"
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[str] = None  # YYYY-MM-DD
    email: Optional[str] = None
    phone: Optional[str] = None
    doctor: Optional[str] = None
    insurance: Optional[str] = None
    member_id: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_date_from: Optional[str] = None
    preferred_date_to: Optional[str] = None
    preferred_time_window: Optional[PreferredTimeWindow] = None
    reason: Optional[str] = None
    needs_followup: bool = False
    followup_question: Optional[str] = None

    @validator("dob", pre=True)
    def normalize_dob(cls, v):
        if not v:
            return None
        try:
            dt = dateparser.parse(v, fuzzy=True)
            return dt.date().isoformat()
        except Exception:
            raise ValueError("dob not parseable")

    @validator("preferred_date", "preferred_date_from", "preferred_date_to", pre=True)
    def normalize_dates(cls, v):
        if not v:
            return None
        try:
            dt = dateparser.parse(v, fuzzy=True)
            return dt.date().isoformat()
        except Exception:
            return None


# ---------------- Deterministic heuristics ----------------
_DOCTOR_CANDIDATES = [
    "Dr Asha Rao", "Dr Meera Iyer", "Dr Vikram Gupta", "Dr Vikram",
    "Asha Rao", "Meera Iyer", "Vikram Gupta"
]
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_RE = re.compile(r"(?:\+?\d{1,4}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{6,12}")
NAME_RE = re.compile(r"\b(?:I am|I'm|this is|my name is)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)", re.I)


def _single_followup_question(missing):
    if not missing:
        return None
    if "name" in missing:
        return "Please provide your full name (first and last)."
    if "dob" in missing:
        return "Please provide your date of birth in YYYY-MM-DD format."
    if "preferred_date" in missing:
        return "When would you like the appointment? Please provide a date (e.g., 2025-09-06) or a short range like 'next 3 days'."
    if "insurance" in missing:
        return "Do you have medical insurance? If yes, please provide provider name and member ID."
    return "Could you provide a contact phone number or email so we can confirm the appointment?"


def _deterministic_parse(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    res: Dict[str, Any] = {"confidence": 0.4, "source": "heuristic"}

    # name
    m = NAME_RE.search(t)
    if m:
        full = m.group(1).strip()
        parts = full.split()
        res["name"] = full
        res["first_name"] = parts[0]
        res["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else None

    # email
    em = EMAIL_RE.search(t)
    if em:
        res["email"] = em.group(0)

    # phone
    ph = PHONE_RE.search(t)
    if ph:
        res["phone"] = ph.group(0)

    # dob
    mdate = re.search(r"(\d{4}-\d{2}-\d{2})", t)
    if mdate:
        res["dob"] = mdate.group(1)
    else:
        m2 = re.search(r"\b(born|dob)\s*[:\-]?\s*([0-9/.\-]{6,12})", t, re.I)
        if m2:
            try:
                dt = dateparser.parse(m2.group(2), fuzzy=True)
                res["dob"] = dt.date().isoformat()
            except Exception:
                pass

    # doctor
    for d in _DOCTOR_CANDIDATES:
        if re.search(re.escape(d), t, re.I):
            res["doctor"] = d
            break

    # insurance
    m_ins = re.search(r"Insurance[:\s]*([A-Za-z0-9 -]+)", t, re.I)
    if m_ins:
        res["insurance"] = m_ins.group(1).strip()

    # preferred date/time
    if re.search(r"\d{4}-\d{2}-\d{2}", t):
        md = re.search(r"(\d{4}-\d{2}-\d{2})", t)
        if md:
            res["preferred_date"] = md.group(1)
    elif re.search(r"\bnext\s+\d+\s+days\b", t, re.I):
        n = int(re.search(r"\d+", t).group(0))
        today = datetime.now().date()
        res["preferred_date_from"] = today.isoformat()
        res["preferred_date_to"] = (today + timedelta(days=n)).isoformat()
    elif re.search(r"\btomorrow\b", t, re.I):
        res["preferred_date"] = (datetime.now().date() + timedelta(days=1)).isoformat()

    if re.search(r"\bmorn(ing)?\b", t, re.I):
        res["preferred_time_window"] = {"start": "09:00", "end": "12:00"}
    if re.search(r"\bafternoon\b", t, re.I):
        res["preferred_time_window"] = {"start": "14:00", "end": "17:00"}

    # reason
    mreason = re.search(r"\b(fever|cough|follow-?up|check-?up|child|initial consult|appointment)\b", t, re.I)
    if mreason:
        res["reason"] = mreason.group(1)

    # followup detection
    missing = []
    if not res.get("name"):
        missing.append("name")
    if not res.get("dob"):
        missing.append("dob")
    if not (res.get("preferred_date") or res.get("preferred_date_from")):
        missing.append("preferred_date")
    if ("initial" in (res.get("reason") or "").lower() or "new" in (res.get("reason") or "").lower()) and not res.get("insurance"):
        missing.append("insurance")

    res["needs_followup"] = bool(missing)
    res["followup_question"] = _single_followup_question(missing)
    return res


# ---------------- LLM wrapper + stronger prompt ----------------
_GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


class GeminiLLM(LLM):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, temperature: float = 0.0):
        super().__init__()
        self.api_key = api_key or _GEMINI_KEY
        self.model = model or _GEMINI_MODEL
        self.temperature = temperature
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        if genai is None:
            raise RuntimeError("google.generativeai not importable; pip install google-generativeai")

    @property
    def _llm_type(self) -> str:
        return "gemini"

    def _call(self, prompt: str, stop: Optional[list] = None) -> str:
        genai.configure(api_key=self.api_key)
        example = {
            "confidence": 0.9,
            "source": "llm",
            "name": "Rajesh Kumar",
            "first_name": "Rajesh",
            "last_name": "Kumar",
            "dob": "1992-05-12",
            "email": "rajesh.k@example.com",
            "phone": "+91-98xxxxxxx",
            "doctor": "Dr Asha Rao",
            "insurance": "HealthPlus",
            "member_id": "HP12345",
            "preferred_date": "2025-09-06",
            "preferred_time_window": {"start": "09:00", "end": "12:00"},
            "reason": "fever",
            "needs_followup": False,
            "followup_question": None
        }
        system = (
            "You MUST return exactly one valid JSON object and nothing else (no markdown, no commentary). "
            "The JSON must use keys matching the example below. Keys may be null when unknown. Dates must be YYYY-MM-DD.\n"
            "Example JSON:"
        )
        full_prompt = f"{system}\n{json.dumps(example, ensure_ascii=False)}\n\nUTTERANCE:\n{prompt}\n\nRETURN JSON ONLY:"
        try:
            resp = genai.generate_text(model=self.model, prompt=full_prompt, temperature=self.temperature)
            txt = getattr(resp, "text", None)
            if not txt and isinstance(resp, dict):
                cands = resp.get("candidates") or []
                if cands:
                    txt = cands[0].get("content") or cands[0].get("text")
            return txt or ""
        except Exception:
            # fallback older API shape
            resp = genai.create(model=self.model, prompt=full_prompt, temperature=self.temperature)
            if isinstance(resp, dict) and "candidates" in resp:
                return resp["candidates"][0].get("content", "")
            return ""


def _extract_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    i = text.find("{")
    j = text.rfind("}")
    if i == -1 or j == -1 or j <= i:
        return None
    return text[i:j+1]


# ---------- tolerant LLM output normalizer ----------
def _camel_to_snake(s: str) -> str:
    s2 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    s3 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s2).lower()
    return re.sub(r'[^a-z0-9_]', '_', s3)


_NORMALIZE_KEY_MAP = {
    "first_name": ["first_name", "firstname", "firstName", "given_name", "givenName", "givenname"],
    "last_name": ["last_name", "lastname", "lastName", "surname", "family_name"],
    "name": ["name", "full_name", "fullName", "displayName"],
    "dob": ["dob", "date_of_birth", "birthdate", "birthday", "dateOfBirth"],
    "email": ["email", "email_address", "emailAddress"],
    "phone": ["phone", "phone_number", "phoneNumber", "tel"],
    "doctor": ["doctor", "doctor_name", "doctorName"],
    "insurance": ["insurance", "insurer", "insurance_provider"],
    "member_id": ["member_id", "memberId", "membership", "policy_number"],
    "preferred_date": ["preferred_date", "date", "appointment_date"],
    "preferred_time_window": ["preferred_time_window", "time_window", "timeWindow"],
    "reason": ["reason", "symptom", "notes", "reason_for_visit"],
    "confidence": ["confidence", "score", "probability"],
    "needs_followup": ["needs_followup", "needsFollowup", "followup_required"],
    "followup_question": ["followup_question", "followupQuestion"],
}


def _normalize_llm_candidate(candidate: dict) -> dict:
    if not isinstance(candidate, dict):
        return {}

    out = {}

    # canonical mapping
    for canonical, variants in _NORMALIZE_KEY_MAP.items():
        for k in variants:
            if k in candidate and candidate[k] not in (None, ""):
                out[canonical] = candidate[k]
                break

    # also map other keys via camel->snake heuristic
    for k, v in candidate.items():
        if v is None:
            continue
        key_snake = _camel_to_snake(k)
        if key_snake in out:
            continue
        # find canonical if snake matches any variant (lower)
        matched = False
        for can, vars in _NORMALIZE_KEY_MAP.items():
            if key_snake in [x.lower() for x in vars]:
                out.setdefault(can, v)
                matched = True
                break
        if not matched:
            out.setdefault(key_snake, v)

    # normalize preferred_time_window strings like "09:00-12:00"
    pw = out.get("preferred_time_window")
    if isinstance(pw, str):
        if "-" in pw:
            parts = pw.split("-", 1)
            out["preferred_time_window"] = {"start": parts[0].strip(), "end": parts[1].strip()}
        elif "," in pw:
            parts = [p.strip() for p in pw.split(",")]
            if len(parts) >= 2:
                out["preferred_time_window"] = {"start": parts[0], "end": parts[1]}
    if "start_time" in out and "preferred_time_window" not in out:
        out["preferred_time_window"] = {"start": out.pop("start_time"), "end": out.pop("end_time", None)}

    # split name into first/last
    if out.get("name") and (not out.get("first_name") and not out.get("last_name")):
        parts = str(out["name"]).strip().split()
        if len(parts) >= 2:
            out["first_name"] = parts[0]
            out["last_name"] = " ".join(parts[1:])
        else:
            out["first_name"] = parts[0]

    # normalize booleans
    if "needs_followup" in out:
        v = out["needs_followup"]
        if isinstance(v, str):
            out["needs_followup"] = v.lower() in ("yes", "true", "1")
        else:
            out["needs_followup"] = bool(v)

    return out


# ---------------- Public API ----------------
def parse_utterance(text: str, use_llm: bool = True) -> ParseResult:
    text = (text or "").strip()
    parsed_obj: Optional[ParseResult] = None
    used_source = "heuristic"

    # Attempt LLM path
    if use_llm and _GEMINI_KEY and genai:
        try:
            gem = GeminiLLM(api_key=_GEMINI_KEY, model=_GEMINI_MODEL, temperature=0.0)
            raw = gem._call(text)
            # log raw LLM output for debugging
            try:
                with open(RAW_LLM_LOG, "a", encoding="utf-8") as f:
                    f.write(f"TS: {datetime.utcnow().isoformat()} UTTERANCE: {text}\nRAW:\n{raw}\n---\n")
            except Exception:
                pass
            jb = _extract_json_block(raw)
            candidate = None
            if jb:
                try:
                    candidate = json.loads(jb)
                except Exception:
                    candidate = None

            if isinstance(candidate, dict):
                # try strict validation, then tolerant normalization
                try:
                    parsed_obj = ParseResult.parse_obj(candidate)
                    used_source = "llm"
                except Exception:
                    # normalization attempt
                    try:
                        norm = _normalize_llm_candidate(candidate)
                        parsed_obj = ParseResult.parse_obj(norm)
                        used_source = "llm"
                    except Exception:
                        parsed_obj = None
        except Exception:
            parsed_obj = None

    # Deterministic fallback
    if parsed_obj is None:
        det = _deterministic_parse(text)
        det.setdefault("source", "heuristic")
        det.setdefault("confidence", 0.4)
        try:
            parsed_obj = ParseResult.parse_obj(det)
            used_source = "heuristic"
        except Exception:
            parsed_obj = ParseResult(source="heuristic", confidence=0.0)

    # ensure followup question where appropriate (priority: name -> dob -> date -> insurance)
    if parsed_obj.needs_followup and not parsed_obj.followup_question:
        missing = []
        if not parsed_obj.name:
            missing.append("name")
        if not parsed_obj.dob:
            missing.append("dob")
        if not (parsed_obj.preferred_date or parsed_obj.preferred_date_from):
            missing.append("preferred_date")
        if ("initial" in (parsed_obj.reason or "").lower() or "new" in (parsed_obj.reason or "").lower()) and not parsed_obj.insurance:
            missing.append("insurance")
        parsed_obj.followup_question = _single_followup_question(missing)

    # log validated parse (audit)
    try:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "utterance": text,
            "parsed": json.loads(parsed_obj.json()),
            "used_source": used_source,
        }
        parse_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        pass

    return parsed_obj


def generate_followup(parsed: ParseResult) -> (bool, Optional[str]):
    missing = []
    if not parsed.name:
        missing.append("name")
    if not parsed.dob:
        missing.append("dob")
    if not (parsed.preferred_date or parsed.preferred_date_from):
        missing.append("preferred_date")
    if ("initial" in (parsed.reason or "").lower() or "new" in (parsed.reason or "").lower()) and not parsed.insurance:
        missing.append("insurance")

    if "name" in missing:
        return True, "Please provide your full name (first and last)."
    if "dob" in missing:
        return True, "Please provide your date of birth in YYYY-MM-DD format."
    if "preferred_date" in missing:
        return True, "When would you like the appointment? Please provide a date (e.g., 2025-09-06) or a short range."
    if "insurance" in missing:
        return True, "Do you have medical insurance? If yes, please share provider name and member ID."
    return False, None
