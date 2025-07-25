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

# Load system prompt for classification
CLASSIFICATION_SYSTEM_PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), "classification_prompt.txt")
try:
    with open(CLASSIFICATION_SYSTEM_PROMPT_FILE_PATH, "r") as f:
        CLASSIFICATION_SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    print(f"Error: {CLASSIFICATION_SYSTEM_PROMPT_FILE_PATH} not found. Please ensure it exists.")
    CLASSIFICATION_SYSTEM_PROMPT = ""

# --- Journal Entry Analysis ---
def analyze_entry(api_key: str, entry: str) -> str:
    """
    Analyzes a journal entry using:
    1. Fuzzy safety keyword match.
    2. AI classification for all other types.

    Returns one of: "safety", "instruction", "quiet", "positive", or "unclear".
    """
    entry_stripped = entry.strip()
    entry_lower = entry_stripped.lower()

    # Step 1: Fuzzy match for safety
    for flag in SAFETY_RED_FLAGS:
        score = fuzz.ratio(entry_lower, flag)
        if score >= FUZZY_MATCH_THRESHOLD:
            print(f"DEBUG: Safety fuzzy match: '{flag}' with score {score}. Returning 'safety'.")
            return "safety"

    if not entry_stripped:
        print("DEBUG: Entry is empty. Returning 'quiet'.")
        return "quiet"

    # Step 2: AI-based classification
    messages = [
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": entry_stripped}
    ]

    try:
        response_text = call_openrouter_api(api_key, messages)
        print(f"DEBUG: Raw AI classification response: '{response_text}'")

        if response_text:
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```json") and cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[7:-3].strip()
            elif cleaned_response.startswith("```") and cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[3:-3].strip()

            try:
                response_json = json.loads(cleaned_response)
                category = response_json.get("category", "").lower()
                print(f"DEBUG: AI classified category: '{category}'")
                if category in ["safety", "instruction", "quiet", "positive"]:
                    return category
                else:
                    return "unclear"
            except json.JSONDecodeError:
                print(f"DEBUG: Failed to parse AI response as JSON: {cleaned_response}")
                return "unclear"
        else:
            return "unclear"

    except Exception as e:
        print(f"DEBUG: Exception during AI classification: {e}")
        return "unclear"

# --- OpenRouter API Call ---
def call_openrouter_api(api_key: str, messages: list) -> Union[str, None]:
    """
    Calls the OpenRouter API and returns the assistant's message content.
    """
    if not api_key:
        print("Error: OpenRouter API key is missing.")
        return None

    formatted_messages = []
    for msg in messages:
        if isinstance(msg['content'], dict):
            formatted_messages.append({
                "role": msg['role'],
                "content": json.dumps(msg['content'])
            })
        else:
            formatted_messages.append(msg)

    try:
        response = requests.post(
            OPENROUTER_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": formatted_messages
            },
            timeout=45
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        print(f"JSON decode error: {json_err} - Response text: {response.text}")
        return None
    except KeyError as key_err:
        print(f"Key error: {key_err} - Response data: {data}")
        return None
    except Exception as e:
        print(f"Unexpected error during API call: {e}")
        return None

# --- Journal Response Wrapper ---
def get_journal_response(api_key: str, system_prompt: str, user_entry: Union[str, dict]) -> Union[str, None]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_entry}
    ]
    return call_openrouter_api(api_key, messages)

# --- Optional Flag-Specific Wrapper (not used anymore but kept if needed) ---
def check_flag(api_key: str, system_prompt_flag: str, user_entry: str) -> Union[str, None]:
    messages = [
        {"role": "system", "content": system_prompt_flag},
        {"role": "user", "content": user_entry}
    ]
    return call_openrouter_api(api_key, messages)
