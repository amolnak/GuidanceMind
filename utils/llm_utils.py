import json
import openai
import hashlib
import os
import re
from datetime import datetime, timedelta

# ------------------ Configuration ------------------

MODEL_NAME = "gpt-4o"  # or "gpt-4o-mini"
CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ------------------ Prompt ------------------

system_msg = (
    "You are a senior regulatory analyst with expertise in FDA and EMA guidance documents.\n"
    "Extract the following fields as structured JSON:\n\n"
    "- Title\n"
    "- Summary\n"
    "- Key Questions and Answers (as a list of strings in the format '1. Purpose: ...', '2. Applicability: ...', etc.)\n"
    "- Issuing Authority\n"
    "- Centers Involved (as a comma-separated string)\n"
    "- Date of Issuance (in 'January 01, 2025' format)\n"
    "- Type of Document\n"
    "- Public Comment Period\n"
    "- Docket Number (search online if necessary; leave blank if unavailable)\n"
    "- Guidance Status\n"
    "- Open for Comment\n"
    "- Comment Closing Date (calculate based on rules below)\n"
    "- Relevance of this Guidance\n\n"
    "**Rules for 'Comment Closing Date':**\n"
    "- If a specific closing date is mentioned, use it as-is.\n"
    "- If a range is mentioned (e.g., 'from Feb 14, 2025 to May 31, 2025'), use the END date as the Comment Closing Date.\n"
    "- If a duration is mentioned (e.g., 'comments accepted for 60 days from issuance'), calculate the closing date by adding that number of days to the 'Date of Issuance'.\n"
    "- If no valid date can be determined, leave the 'Comment Closing Date' field blank.\n\n"
    "**Rules for 'Date of Issuance':**\n"
    "- it should be in January 01, 2025.\n"
    "**Rules for 'Docket Number':**\n"
    "- You need to search over the inernet.\n"
    "Return ONLY valid JSON. Do not include explanations or markdown."
)

# ------------------ Helper: Validate JSON ------------------

def validate_json(raw_response):
    try:
        parsed = json.loads(raw_response)
        return parsed
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parsing error: {e}")
        return {"error": "Invalid JSON", "raw_response": raw_response}

# ------------------ Main LLM Function ------------------

def extract_pdf_details(text, api_key):
    openai.api_key = api_key

    # ✅ Use cached response if available
    cached = load_from_cache(text)
    if cached:
        print("✅ Using cached result.")
        return cached

    try:
        print("⏳ Calling OpenAI:", MODEL_NAME)
        response = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )

        raw = response['choices'][0]['message']['content'].strip()

        # ✅ Remove markdown code block if present
        if raw.startswith("```json"):
            raw = raw.lstrip("```json").strip()
        if raw.startswith("```"):
            raw = raw.lstrip("```").strip()
        if raw.endswith("```"):
            raw = raw.rstrip("```").strip()

        parsed = validate_json(raw)

        if "error" in parsed:
            return parsed  # Return error if JSON is invalid

        # ✅ Apply formatters
        parsed = add_comment_closing_date(parsed)
        parsed = format_key_questions(parsed)
        parsed = format_centers_involved(parsed)

        # ✅ Cache it
        save_to_cache(text, parsed)

        return parsed

    except Exception as e:
        return {"error": str(e)}

# ------------------ Helper: Format Q&A ------------------

def format_key_questions(data):
    qa = data.get("Key Questions and Answers")
    if isinstance(qa, dict):
        formatted = []
        numbered = [
            ("Purpose", 1),
            ("Applicability", 2),
            ("Defining Phases", 3),
            ("Use of Process Models", 4),
            ("FDA on Advanced Manufacturing", 5)
        ]
        for key, num in numbered:
            if key in qa:
                formatted.append(f"{num}. {key}: {qa[key]}")
        data["Key Questions and Answers"] = formatted
    return data

# ------------------ Helper: Cache Logic ------------------

def get_cache_path(text):
    hash_val = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{hash_val}.json")

def load_from_cache(text):
    path = get_cache_path(text)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_to_cache(text, result):
    path = get_cache_path(text)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

# ------------------ Helper: Format Centers ------------------

def format_centers_involved(data):
    centers = data.get("Centers Involved")
    if isinstance(centers, list):
        data["Centers Involved"] = ", ".join(centers)
    return data

# ------------------ Helper: Date Parser ------------------

def add_comment_closing_date(data):
    try:
        # Step 1: Parse Issuance Date
        date_str = data.get("Date of Issuance", "")
        parsed_date = None
        for fmt in ("%B %d, %Y", "%Y-%m-%d", "%B %d,%Y", "%B %Y"):
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                if fmt == "%B %Y":
                    parsed_date = parsed_date.replace(day=1)
                break
            except ValueError:
                continue

        if not parsed_date:
            raise ValueError("Invalid issuance date")

        # Save normalized issuance date
        data["Parsed Issuance Date"] = parsed_date.strftime("%B %d, %Y")

        # Step 2: Validate Comment Closing Date (if already provided)
        closing_str = data.get("Comment Closing Date", "")
        try:
            # If already valid, keep it
            datetime.strptime(closing_str, "%B %d, %Y")
            return data  # ✅ All good — use the LLM's date
        except Exception:
            pass  # LLM date is missing or invalid — go to fallback

        # Step 3: Fallback: calculate from Public Comment Period
        comment_period = data.get("Public Comment Period", "").lower()
        match = re.search(r"(\d+)\s+days", comment_period)
        if match:
            days = int(match.group(1))
            closing_date = parsed_date + timedelta(days=days)
            data["Comment Closing Date"] = closing_date.strftime("%B %d, %Y")
        else:
            data["Comment Closing Date"] = "Not specified"

    except Exception:
        data["Parsed Issuance Date"] = "Error parsing date"
        data["Comment Closing Date"] = "Error calculating date"

    return data