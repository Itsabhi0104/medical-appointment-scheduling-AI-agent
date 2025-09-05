import os
import re
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
from dateutil import parser as dateparser
import google.generativeai as genai

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PreferredTimeWindow(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None

class ParseResult(BaseModel):
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source: str = Field("heuristic")
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[str] = None  # Patient's date of birth
    email: Optional[str] = None
    phone: Optional[str] = None
    doctor: Optional[str] = None
    insurance: Optional[str] = None
    member_id: Optional[str] = None
    preferred_date: Optional[str] = None  # Appointment date (NOT DOB)
    preferred_date_from: Optional[str] = None
    preferred_date_to: Optional[str] = None
    preferred_time_window: Optional[PreferredTimeWindow] = None
    reason: Optional[str] = None
    needs_followup: bool = False
    followup_question: Optional[str] = None

    @validator("dob", pre=True, always=True)
    def normalize_dob(cls, v):
        if not v:
            return None
        try:
            dt = dateparser.parse(str(v), fuzzy=True)
            # DOB should be in the past
            if dt and dt.date() < datetime.now().date():
                return dt.date().isoformat()
        except Exception:
            pass
        return None

    @validator("preferred_date", pre=True, always=True)
    def normalize_preferred_date(cls, v):
        if not v:
            return None
        try:
            dt = dateparser.parse(str(v), fuzzy=True)
            # Preferred date should be today or future
            if dt and dt.date() >= datetime.now().date():
                return dt.date().isoformat()
        except Exception:
            pass
        return None

class EnhancedNLUAgent:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        # Doctor names for matching
        self.doctors = [
            "Dr Asha Rao", "Dr Meera Iyer", "Dr Vikram Gupta", 
            "Dr Vikram", "Asha Rao", "Meera Iyer", "Vikram Gupta"
        ]
        
        # Regex patterns
        self.email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
        self.phone_pattern = re.compile(r'(?:\+?\d{1,4}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{6,12}')
        self.name_pattern = re.compile(r'\b(?:I am|I\'m|this is|my name is|name:|I\'m)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)', re.I)
        
    def _extract_dates(self, text: str) -> Dict[str, str]:
        """Extract and separate DOB from appointment dates"""
        dates = {}
        
        # Look for explicit DOB patterns
        dob_patterns = [
            r'\b(?:DOB|dob|date of birth|born)[:\s]+([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})',
            r'\b([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})\b.*(?:DOB|dob|born)',
            r'\b(?:DOB|dob)[:\s]*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})'
        ]
        
        for pattern in dob_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    dt = dateparser.parse(match.group(1))
                    if dt and dt.date() < datetime.now().date():
                        dates['dob'] = dt.date().isoformat()
                        break
                except:
                    continue
        
        # Look for appointment date patterns
        apt_patterns = [
            r'\b(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
            r'\b(tomorrow|today)',
            r'\b([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})\b(?!.*(?:DOB|dob|born))',
            r'\b(in\s+\d+\s+days?)',
            r'\b(next\s+\d+\s+days?)'
        ]
        
        today = datetime.now().date()
        
        for pattern in apt_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                date_str = match.group(1).lower()
                try:
                    if 'next tuesday' in date_str:
                        days_ahead = (1 - today.weekday()) % 7  # Tuesday = 1
                        if days_ahead == 0:
                            days_ahead = 7
                        dates['preferred_date'] = (today + timedelta(days=days_ahead)).isoformat()
                    elif 'tomorrow' in date_str:
                        dates['preferred_date'] = (today + timedelta(days=1)).isoformat()
                    elif 'today' in date_str:
                        dates['preferred_date'] = today.isoformat()
                    elif 'next' in date_str and 'days' in date_str:
                        days = int(re.search(r'\d+', date_str).group())
                        dates['preferred_date_from'] = today.isoformat()
                        dates['preferred_date_to'] = (today + timedelta(days=days)).isoformat()
                    else:
                        dt = dateparser.parse(date_str)
                        if dt and dt.date() >= today:
                            dates['preferred_date'] = dt.date().isoformat()
                except:
                    continue
                break
        
        return dates

    def _extract_time_preferences(self, text: str) -> Optional[PreferredTimeWindow]:
        """Extract time preferences from text"""
        text_lower = text.lower()
        
        if 'morning' in text_lower:
            return PreferredTimeWindow(start="09:00", end="12:00")
        elif 'afternoon' in text_lower:
            return PreferredTimeWindow(start="12:00", end="17:00")
        elif 'evening' in text_lower:
            return PreferredTimeWindow(start="17:00", end="20:00")
        
        return None

    def _extract_entities_heuristic(self, text: str) -> Dict[str, Any]:
        """Extract entities using rule-based approach"""
        result = {
            'confidence': 0.6,
            'source': 'heuristic'
        }
        
        # Extract name
        name_match = self.name_pattern.search(text)
        if name_match:
            full_name = name_match.group(1).strip()
            parts = full_name.split()
            result['name'] = full_name
            result['first_name'] = parts[0]
            if len(parts) > 1:
                result['last_name'] = ' '.join(parts[1:])
        
        # Extract contact info
        email_match = self.email_pattern.search(text)
        if email_match:
            result['email'] = email_match.group(0)
        
        phone_match = self.phone_pattern.search(text)
        if phone_match:
            result['phone'] = phone_match.group(0)
        
        # Extract doctor
        for doctor in self.doctors:
            if re.search(re.escape(doctor), text, re.I):
                result['doctor'] = doctor
                break
        
        # Extract dates
        dates = self._extract_dates(text)
        result.update(dates)
        
        # Extract time preferences
        time_pref = self._extract_time_preferences(text)
        if time_pref:
            result['preferred_time_window'] = time_pref.dict()
        
        # Extract insurance
        insurance_match = re.search(r'insurance[:\s]+([A-Za-z0-9\s]+)', text, re.I)
        if insurance_match:
            result['insurance'] = insurance_match.group(1).strip()
        
        member_match = re.search(r'member[:\s]+([A-Za-z0-9]+)', text, re.I)
        if member_match:
            result['member_id'] = member_match.group(1).strip()
        
        # Extract reason
        reason_patterns = [
            r'\bfor\s+(fever|cough|checkup|follow-?up|consultation|initial\s+consult)',
            r'\b(fever|cough|checkup|follow-?up|consultation)\b'
        ]
        
        for pattern in reason_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                result['reason'] = match.group(1).lower()
                break
        
        return result

    def _extract_entities_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract entities using Gemini LLM"""
        if not self.gemini_key:
            return None
        
        try:
            genai.configure(api_key=self.gemini_key)
            
            prompt = f"""
Extract medical appointment information from this text. Return ONLY a JSON object with these fields:

{{
  "name": "full name",
  "first_name": "first name only",
  "last_name": "last name only",
  "dob": "YYYY-MM-DD format for date of birth (NOT appointment date)",
  "email": "email address",
  "phone": "phone number",
  "doctor": "doctor name",
  "insurance": "insurance provider",
  "member_id": "insurance member ID", 
  "preferred_date": "YYYY-MM-DD for appointment date (NOT date of birth)",
  "preferred_date_from": "start of date range",
  "preferred_date_to": "end of date range",
  "preferred_time_window": {{"start": "HH:MM", "end": "HH:MM"}},
  "reason": "reason for appointment",
  "confidence": 0.8
}}

IMPORTANT: 
- DOB is the patient's birth date (usually in the past)
- preferred_date is when they want the appointment (usually future)
- Don't confuse these two dates!

Text: "{text}"

JSON only:
"""
            
            model = genai.GenerativeModel(self.gemini_model)
            response = model.generate_content(prompt)
            
            if response and response.text:
                # Extract JSON from response
                json_text = response.text.strip()
                if json_text.startswith('```json'):
                    json_text = json_text[7:-3]
                elif json_text.startswith('```'):
                    json_text = json_text[3:-3]
                
                try:
                    result = json.loads(json_text)
                    result['source'] = 'llm'
                    return result
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM JSON: {json_text}")
                    return None
        
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return None

    def _determine_followup(self, parsed: ParseResult) -> tuple[bool, Optional[str]]:
        """Determine if followup is needed and what question to ask"""
        missing_fields = []
        
        # Check required fields
        if not parsed.first_name or not parsed.last_name:
            missing_fields.append("name")
        
        if not parsed.dob:
            missing_fields.append("dob")
        
        if not parsed.preferred_date and not parsed.preferred_date_from:
            missing_fields.append("date")
        
        # For new patients, require insurance
        if parsed.reason and ('initial' in parsed.reason or 'new' in parsed.reason):
            if not parsed.insurance:
                missing_fields.append("insurance")
        
        if not missing_fields:
            return False, None
        
        # Prioritized followup questions
        if "name" in missing_fields:
            return True, "Please provide your full name (first and last name)."
        elif "dob" in missing_fields:
            return True, "Please provide your date of birth (YYYY-MM-DD format)."
        elif "date" in missing_fields:
            return True, "When would you like to schedule the appointment? Please provide a specific date or date range."
        elif "insurance" in missing_fields:
            return True, "Do you have medical insurance? If yes, please provide the provider name and member ID."
        
        return True, "Could you provide additional information to complete your booking?"

    def parse_utterance(self, text: str, use_llm: bool = True) -> ParseResult:
        """Main parsing function"""
        text = text.strip()
        
        # Try LLM first if available
        parsed_data = None
        if use_llm:
            parsed_data = self._extract_entities_llm(text)
        
        # Fallback to heuristic
        if not parsed_data:
            parsed_data = self._extract_entities_heuristic(text)
        
        # Create ParseResult object
        try:
            parsed = ParseResult(**parsed_data)
        except Exception as e:
            logger.error(f"Failed to create ParseResult: {e}")
            parsed = ParseResult(confidence=0.1, source="error")
        
        # Determine followup
        needs_followup, followup_question = self._determine_followup(parsed)
        parsed.needs_followup = needs_followup
        parsed.followup_question = followup_question
        
        # Log the parse result
        logger.info(f"Parsed: {parsed.dict()}")
        
        return parsed

# Global instance
nlu_agent = EnhancedNLUAgent()

# Backward compatibility functions
def parse_utterance(text: str, use_llm: bool = True) -> ParseResult:
    return nlu_agent.parse_utterance(text, use_llm)

def generate_followup(parsed: ParseResult) -> tuple[bool, Optional[str]]:
    return nlu_agent._determine_followup(parsed)