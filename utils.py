# utils.py
import requests
import json
import os
import streamlit as st
import subprocess
from thefuzz import fuzz
from typing import Union
from datetime import datetime
import csv
from supabase import create_client, Client

# --- Supabase Configuration ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Constants ---
SYSTEM_PROMPT_VERSION = "v1.0"
USER_PROMPT_VERSION = "v1.0-session"

SAFETY_RED_FLAGS = [
    "end it all", "kill myself", "suicide", "worthless", "can't go on", "hopeless",
    "despair", "give up", "death", "die", "harm myself", "self harm", "unalive",
    "kms", "i wanna die"
]
FUZZY_MATCH_THRESHOLD = 80

# --- Logging ---
def log_to_csv(prompt, entry, category, response_text, safety_flagged):
    log_file_path = os.path.join(os.path.dirname(__file__), "logs", "responses_log.csv")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    fieldnames = ["timestamp", "prompt", "entry", "category", "response_text", "safety_flagged"]

    with open(log_file_path, mode='a', newline='', encoding='utf-8-sig') as log_file:
        log_writer = csv.DictWriter(log_file, fieldnames=fieldnames)
        if log_file.tell() == 0:  # Check if file is empty
            log_writer.writeheader()  # Write header only if file is empty

        log_writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "entry": entry,
            "category": category,
            "response_text": response_text,
            "safety_flagged": safety_flagged
        })

def log_to_supabase(session_id, prompt, entry, category, response_text, safety_flagged):
    try:
        supabase.table("logs").insert({
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "entry": entry,
            "category": category,
            "response_text": response_text,
            "safety_flagged": safety_flagged,
            "system_prompt_version": SYSTEM_PROMPT_VERSION,
            "user_prompt_version": USER_PROMPT_VERSION,
            "session_id": session_id
        }).execute()
    except Exception as e:
        print("❌ Supabase logging failed:", e)


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
def classify_and_respond(api_key: str, session_id: str, prompts: list[str], conversation: dict[int, str]) -> dict:
    last_prompt_index = len(prompts) - 1
    last_entry = conversation[last_prompt_index]

    # Fuzzy match against safety keywords before API call
    for red_flag in SAFETY_RED_FLAGS:
        similarity = fuzz.partial_ratio(last_entry.lower(), red_flag)
        if similarity >= FUZZY_MATCH_THRESHOLD:
            log_to_csv(
                prompt=prompt,
                entry=last_entry,
                category="safety",
                response_text="🚨 You mentioned something serious. Please talk to someone you trust or reach out for support.",
                safety_flagged=True
            )
            log_to_supabase(
                session_id=session_id,
                prompt=prompt,
                entry=last_entry,
                category="safety",
                response_text="🚨 You mentioned something serious. Please talk to someone you trust or reach out for support.",
                safety_flagged=True
            )
            return {
                "category": "safety",
                "response_text": (
                    "🚨 You mentioned something serious. Please talk to someone you trust or reach out for support."
                )
            }

    # Skip if prompts aren't loaded
    if not SYSTEM_PROMPT or not USER_PROMPT_TEMPLATE:
        return {"category": "unclear", "response_text": "Missing prompt templates."}

    # Build reflections
    reflections = ""
    for index, prompt in enumerate(prompts):
        reflections += f"Reflection #{index+1}. " + f"Your journal prompt is: **\"{prompt.strip()}\"**."  + f"The user's entry is: **\"{conversation[index]}\"**\n"

    user_prompt = (
        USER_PROMPT_TEMPLATE
        .replace("{{reflections}}", reflections.strip())
    )

    print(reflections)

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

        parsed = json.loads(cleaned)

        log_to_csv(
            prompt=prompt,
            entry=last_entry,
            category=parsed.get("category", "unknown"),
            response_text=parsed.get("response_text", ""),
            safety_flagged=False
        )
        log_to_supabase(
            session_id=session_id,
            prompt=prompt,
            entry=last_entry,
            category=parsed.get("category", "unknown"),
            response_text=parsed.get("response_text", ""),
            safety_flagged=False
        )

        return parsed

    except Exception as e:
        print(f"Error parsing AI response: {e}")

        log_to_csv(
            prompt=prompt,
            entry=last_entry,
            category="unclear",
            response_text="Parsing error.",
            safety_flagged=False
        )
        log_to_supabase(
            session_id=session_id,
            prompt=prompt,
            entry=last_entry,
            category="unclear",
            response_text="Parsing error.",
            safety_flagged=False
        )

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


def get_version_info(session_id: str):
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
    st.caption(f"{SYSTEM_PROMPT_VERSION} 🔸 {USER_PROMPT_VERSION} 🔸 {commit} 🔸 {session_id}")