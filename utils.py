# utils.py
import requests
import json
import os
from thefuzz import fuzz
from typing import Union

# --- Constants ---
SAFETY_RED_FLAGS = [
    "end it all", "kill myself", "suicide", "worthless", "can't go on", "hopeless",
    "despair", "give up", "death", "die", "harm myself", "self harm", "unalive",
    "kms", "i wanna die"
]
FUZZY_MATCH_THRESHOLD = 80

# OpenRouter API settings
OPENROUTER_API_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-3.2-3b-instruct"

# Load Prompts
SYSTEM_PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
USER_PROMPT_TEMPLATE_FILE_PATH = os.path.join(os.path.dirname(__file__), "user_prompt.txt")

try:
    with open(SYSTEM_PROMPT_FILE_PATH, "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    print(f"Error: {SYSTEM_PROMPT_FILE_PATH} not found.")
    SYSTEM_PROMPT = ""

try:
    with open(USER_PROMPT_TEMPLATE_FILE_PATH, "r") as f:
        USER_PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    print(f"Error: {USER_PROMPT_TEMPLATE_FILE_PATH} not found.")
    USER_PROMPT_TEMPLATE = ""

# --- Main Classifier + Response Generator ---
def classify_and_respond(api_key: str, prompt: str, entry: str) -> dict:
    entry_stripped = entry.strip().lower()

    # Fuzzy match against safety keywords before API call
    for red_flag in SAFETY_RED_FLAGS:
        similarity = fuzz.partial_ratio(entry_stripped, red_flag)
        if similarity >= FUZZY_MATCH_THRESHOLD:
            return {
                "category": "safety",
                "response_text": (
                    "🚨 You mentioned something serious. Please talk to someone you trust or reach out for support."
                )
            }

    # Skip if prompts aren't loaded
    if not SYSTEM_PROMPT or not USER_PROMPT_TEMPLATE:
        return {"category": "unclear", "response_text": "Missing prompt templates."}

    # Build user prompt
    user_prompt = (
        USER_PROMPT_TEMPLATE
        .replace("{{prompt}}", prompt.strip())
        .replace("{{user_entry}}", entry.strip())
    )

    # Construct and send to OpenRouter
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    raw_response = call_openrouter_api(api_key, messages)
    if not raw_response:
        return {"category": "unclear", "response_text": "Couldn’t reach the AI."}

    try:
        cleaned = raw_response.strip("` \n")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

        # Remove common formatting artifacts
        if cleaned.startswith("```json"):
            cleaned = cleaned.replace("```json", "").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        return json.loads(cleaned)

    except Exception as e:
        print(f"Error parsing AI response: {e}")
        return {"category": "unclear", "response_text": "Parsing error."}

# --- OpenRouter API Helper ---
def call_openrouter_api(api_key: str, messages: list) -> Union[str, None]:
    if not api_key:
        print("Missing OpenRouter API key.")
        return None

    try:
        response = requests.post(
            OPENROUTER_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": messages
            },
            timeout=45
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"API error: {e}")
        return None
