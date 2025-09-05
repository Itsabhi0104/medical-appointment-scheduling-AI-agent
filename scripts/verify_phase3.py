from dotenv import load_dotenv
load_dotenv()

from backend.agents.flow import run_booking_flow
import os
import json

SAMPLES = [
    "Hi I'm Rajesh Kumar, DOB 1992-05-12. I want to see Dr Asha Rao next Tuesday morning for a fever. My email is rajesh.k@example.com",
    "Hello this is Anjali Iyer, 1990-03-18, need follow-up with Dr Vikram Gupta. Phone +919812345678",
    "I am Navya. Can I book with Dr Meera Iyer on 2025-09-06? Insurance: HealthPlus, member HP12345",
    "Need an appointment for a child, Dr Asha Rao preferred, any slot next week for 30 minutes. Call me at 09876543210",
    "Hi, I'm a new patient and want to schedule initial consult. Prefer Dr Vikram, available any afternoon next 3 days.",
]

def run_samples(use_llm: bool):
    print(f"\n=== Running samples (use_llm={use_llm}) ===\n")
    for i, s in enumerate(SAMPLES, 1):
        print(f"--- Sample #{i}: {s}\n")
        out = run_booking_flow(s, use_llm=use_llm, max_suggestions=5)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        print("\n")

def main():
    run_samples(use_llm=False)

    gemkey = os.environ.get("GEMINI_API_KEY")
    try:
        import google.generativeai as genai  # noqa
        genai_ok = True
    except Exception:
        genai_ok = False

    if gemkey and genai_ok:
        run_samples(use_llm=True)
    else:
        print("\nSkipping LLM path: ensure google-generativeai is installed in this venv and GEMINI_API_KEY is set in .env\n")

if __name__ == "__main__":
    main()
