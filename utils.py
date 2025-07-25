# utils.py
import requests
import json
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # Keep for potential fallback/secondary checks if needed, but primary analysis shifts to AI
from typing import Union

# Initialize the VADER sentiment analyzer (kept for now, but its primary role in analyze_entry will change)
analyzer = SentimentIntensityAnalyzer()

# --- Constants ---
# Keywords and phrases for entry analysis (these lists will now be less critical, as AI handles nuance)
# Kept for very basic initial checks or as fallback if AI classification fails
SAFETY_RED_FLAGS = ["end it all", "kill myself", "suicide", "worthless", "can't go on", "hopeless", "despair", "give up", "death", "die", "harm myself", "self harm", "unalive", "kms", "slewerslide"]
TECH_KEYWORDS = ["react", "javascript", "python", "html", "api", "component", "code", "bug", "error", "debug", "function", "variable"]
INSTRUCTION_PHRASES = [
    "write me", "how do i", "generate", "make this", "summarise", "explain",
    "create a", "give me", "tell me about", "joke", "tell me a joke", "what is",
    "how are you", "what's up", "hi", "hello", "hey", "good morning", "good evening",
    "how's it going", "what's your name", "who are you"
]
QUIET_RESPONSES = ["ok", "fine", ".", "...", "idk", "nah", "nope", "nothing", "", " "]

SHORT_ENTRY_LENGTH_THRESHOLD = 15

# OpenRouter API settings
OPENROUTER_API_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-3.2-3b-instruct"

# Load the new classification system prompt
CLASSIFICATION_SYSTEM_PROMPT_FILE = "classification_prompt.txt"
try:
    with open(CLASSIFICATION_SYSTEM_PROMPT_FILE, "r") as f:
        CLASSIFICATION_SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    print(f"Error: {CLASSIFICATION_SYSTEM_PROMPT_FILE} not found. Please ensure it exists.")
    CLASSIFICATION_SYSTEM_PROMPT = "" # Fallback to empty if file not found

# --- Journal Entry Analysis (Now AI-Powered) ---
def analyze_entry(api_key: str, entry: str) -> str:
    """
    Analyzes a journal entry using AI for safety concerns, instructional intent,
    quiet responses, or positive sentiment.

    Args:
        api_key (str): Your OpenRouter API key.
        entry (str): The user's journal entry.

    Returns:
        str: A string indicating the outcome: "safety", "instruction", "quiet", or "positive".
             Defaults to "quiet" if AI classification fails or is ambiguous.
    """
    entry_stripped = entry.strip()

    if not entry_stripped: # Handle empty entries immediately without AI call
        return "quiet"

    # Use AI to classify the entry's intent
    messages = [
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": entry_stripped}
    ]

    try:
        response_text = call_openrouter_api(api_key, messages)
        if response_text:
            # Attempt to parse the JSON response from the AI
            response_json = json.loads(response_text)
            category = response_json.get("category", "").lower()

            if category in ["safety", "instruction", "quiet", "positive"]:
                return category
            else:
                print(f"AI returned an unexpected category: {category}. Defaulting to 'quiet'.")
                return "quiet" # Fallback for unexpected AI category
        else:
            print("AI classification response was empty. Defaulting to 'quiet'.")
            return "quiet" # Fallback if AI call returns None

    except json.JSONDecodeError:
        print(f"AI classification response was not valid JSON: {response_text}. Defaulting to 'quiet'.")
        return "quiet" # Fallback for malformed JSON from AI
    except Exception as e:
        print(f"Error during AI classification: {e}. Defaulting to 'quiet'.")
        return "quiet" # General fallback for any other error during classification

# --- OpenRouter API Calls (remains the same) ---
def call_openrouter_api(api_key: str, messages: list) -> Union[str, None]:
    """
    Makes a call to the OpenRouter API with a list of messages.

    Args:
        api_key (str): Your OpenRouter API key.
        messages (list): A list of message dictionaries (e.g., [{"role": "system", "content": "..."}]).
                         The 'content' field can now be a string or a JSON-serializable dictionary.

    Returns:
        str | None: The content of the AI's response message, or None if an error occurs.
    """
    if not api_key:
        print("Error: OpenRouter API key is missing.")
        return None

    # Ensure messages content is correctly formatted (string or JSON string)
    formatted_messages = []
    for msg in messages:
        if isinstance(msg['content'], dict):
            formatted_messages.append({
                "role": msg['role'],
                "content": json.dumps(msg['content']) # Convert dict content to JSON string
            })
        else:
            formatted_messages.append(msg) # Keep string content as is

    try:
        response = requests.post(
            OPENROUTER_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": formatted_messages # Use the formatted messages
            },
            timeout=45 # Increased timeout slightly for potentially longer responses
        )
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
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
        print(f"An unexpected request error occurred: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        print(f"JSON decode error: {json_err} - Response text: {response.text}")
        return None
    except KeyError as key_err:
        print(f"Key error in API response structure: {key_err} - Response data: {data}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during API call: {e}")
        return None

# --- Specific API Call Wrappers (for clarity in app.py) ---
def get_journal_response(api_key: str, system_prompt: str, user_entry: Union[str, dict]) -> Union[str, None]:
    """
    Calls OpenRouter to get a journaling assistant response.
    User entry can now be a string or a dictionary for structured input.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_entry} # user_entry can now be dict or string
    ]
    return call_openrouter_api(api_key, messages)

def check_flag(api_key: str, system_prompt_flag: str, user_entry: str) -> Union[str, None]:
    """
    Calls OpenRouter to check a specific flag (e.g., mental health crisis, instruction).
    """
    messages = [
        {"role": "system", "content": system_prompt_flag},
        {"role": "user", "content": user_entry}
    ]
    return call_openrouter_api(api_key, messages)
