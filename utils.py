# utils.py
import requests
import json
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import Union

# Initialize the VADER sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# --- Constants ---
# Keywords and phrases for entry analysis
SAFETY_RED_FLAGS = ["end it all", "kill myself", "suicide", "worthless", "can't go on", "hopeless", "despair", "give up"]
TECH_KEYWORDS = ["react", "javascript", "python", "html", "api", "component", "code", "bug", "error", "debug", "function", "variable"]
INSTRUCTION_PHRASES = ["write me", "how do i", "generate", "make this", "summarise", "explain", "create a", "give me", "tell me about"]
QUIET_RESPONSES = ["ok", "fine", ".", "...", "idk", "nah", "nope", "nothing", "", " "] # Added empty string and space for robustness

# Define a threshold for what constitutes a "short" entry for the purpose of prompting deeper reflection
SHORT_ENTRY_LENGTH_THRESHOLD = 15 # Entries shorter than this (excluding leading/trailing spaces) will be considered "quiet"

# OpenRouter API settings
OPENROUTER_API_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
# Updated model to Meta: Llama 3.2 3B Instruct
OPENROUTER_MODEL = "meta-llama/llama-3.2-3b-instruct"

# --- Journal Entry Analysis ---
def analyze_entry(entry: str) -> str:
    """
    Analyzes a journal entry for safety concerns, instructional intent,
    quiet responses, or positive sentiment.

    Args:
        entry (str): The user's journal entry.

    Returns:
        str: A string indicating the outcome: "safety", "instruction", "quiet", or "positive".
    """
    entry_lower = entry.strip().lower()
    entry_length = len(entry.strip())

    # 1. Check for safety red flags (highest priority)
    if any(flag in entry_lower for flag in SAFETY_RED_FLAGS):
        return "safety"

    # 2. Check for instructional or technical content
    if any(word in entry_lower for word in TECH_KEYWORDS) or \
       any(phrase in entry_lower for phrase in INSTRUCTION_PHRASES):
        return "instruction"

    # 3. Check for exact quiet phrases OR if the entry is very short
    if entry_lower in QUIET_RESPONSES or entry_length < SHORT_ENTRY_LENGTH_THRESHOLD:
        return "quiet"

    # 4. Perform sentiment analysis for general negative sentiment that might indicate safety
    sentiment = analyzer.polarity_scores(entry)
    if sentiment['compound'] < -0.3: # Strong negative sentiment
        return "safety"

    # 5. If sentiment is not clearly positive, route to 'quiet' for AI encouragement
    if sentiment['compound'] <= 0.3: # If compound score is not greater than 0.3 (i.e., neutral or negative)
        return "quiet"

    # 6. If none of the above conditions are met, the entry is genuinely positive
    return "positive"

# --- OpenRouter API Calls ---
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
