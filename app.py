# app.py
import streamlit as st
import json
import os
from utils import analyze_entry, get_journal_response, check_flag
from typing import Union # Import Union for type hinting

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Bluum Journal", layout="centered")
st.title("🪴 Bluum Daily Reflection")

# --- Constants and File Loading ---
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "prompts.json")
SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
CLASSIFICATION_SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "classification_prompt.txt") # NEW

try:
    with open(PROMPTS_FILE, "r") as f:
        PROMPTS = json.load(f)
except FileNotFoundError:
    st.error(f"Error: {PROMPTS_FILE} not found. Please ensure it exists.")
    st.stop()

try:
    with open(SYSTEM_PROMPT_FILE, "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    st.error(f"Error: {SYSTEM_PROMPT_FILE} not found. Please ensure it exists.")
    st.stop()

# --- API Key Handling ---
api_key = st.secrets.get("OPENROUTER_API_KEY")
if not api_key:
    st.warning("Please set your OpenRouter API key in the Streamlit secrets.toml file.")
    st.info("Example: \n\n```toml\n[secrets]\nOPENROUTER_API_KEY = \"sk-your-api-key\"\n```")
    st.stop()

# --- Session State Initialization ---
# Define the possible states of the application flow
APP_STATES = ["initial", "entry_submitted", "followup_submitted"]

# Initialize all necessary session state variables
if "app_state" not in st.session_state:
    st.session_state.app_state = "initial" # Controls which part of the UI is shown
if "journal_entry_text" not in st.session_state:
    st.session_state.journal_entry_text = ""
if "ai_initial_response" not in st.session_state:
    st.session_state.ai_initial_response = ""
if "followup_entry_text" not in st.session_state:
    st.session_state.followup_entry_text = ""
if "ai_followup_response" not in st.session_state:
    st.session_state.ai_followup_response = ""
if "mood_selected" not in st.session_state:
    st.session_state.mood_selected = list(PROMPTS.keys())[0]
if "current_prompt" not in st.session_state:
    st.session_state.current_prompt = PROMPTS[st.session_state.mood_selected][0]
if "error_message" not in st.session_state: # General error message for API issues
    st.session_state.error_message = ""
if "current_reflection_concluded" not in st.session_state: # NEW: Flag to explicitly track if reflection chain is concluded
    st.session_state.current_reflection_concluded = False

# --- Helper Functions for State Transitions and Actions ---
def set_app_state(state: str):
    """Changes the application's state."""
    if state in APP_STATES:
        st.session_state.app_state = state
    else:
        st.error(f"Invalid app state: {state}")

def reset_app():
    """Resets all session state variables to restart the application."""
    keys_to_reset = [
        "app_state", "journal_entry_text", "ai_initial_response",
        "followup_entry_text", "ai_followup_response", "error_message",
        "current_reflection_concluded" # Reset this flag too
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state.app_state = "initial"
    st.session_state.journal_entry_text = ""
    st.session_state.ai_initial_response = ""
    st.session_state.followup_entry_text = ""
    st.session_state.ai_followup_response = ""
    st.session_state.mood_selected = list(PROMPTS.keys())[0]
    st.session_state.current_prompt = PROMPTS[st.session_state.mood_selected][0]
    st.session_state.error_message = ""
    st.session_state.current_reflection_concluded = False # Ensure it's reset
    st.rerun() # Force a rerun to clear the UI

def get_ai_response_and_set_state(user_input_for_ai: Union[str, dict], is_followup: bool = False):
    """
    Fetches AI response and updates the appropriate session state variable.
    Handles general AI responses and follow-up responses.
    The `user_input_for_ai` is the content that goes into the 'user' role of the API call.
    It can now be a string or a dictionary for structured input.
    """
    st.session_state.error_message = "" # Clear previous errors
    response_target_key = "ai_followup_response" if is_followup else "ai_initial_response"
    
    with st.spinner("Generating response..."):
        response = get_journal_response(api_key, SYSTEM_PROMPT, user_input_for_ai)

    if response:
        st.session_state[response_target_key] = response
        if not is_followup:
            set_app_state("entry_submitted")
        else:
            set_app_state("followup_submitted")
            # Do NOT clear followup_entry_text here, it will be cleared based on outcome in handle_followup_submission
        st.rerun() # Force a rerun immediately after state is updated with AI response
    else:
        st.session_state.error_message = (
            "⚠️ We hit a snag talking to the journaling assistant. "
            "This might be due to an API error or the free model's rate limit (1 request/minute). "
            "Please check your terminal for details and try again in a minute."
        )

def handle_initial_submission():
    """Handles the submission of the initial journal entry."""
    st.session_state.error_message = "" # Clear previous errors
    if not st.session_state.journal_entry_text.strip():
        st.warning("Please write something before submitting.")
        return

    # Ensure reflection is not marked as concluded for a new submission
    st.session_state.current_reflection_concluded = False

    with st.spinner("Analyzing your entry..."):
        # Use AI-powered analyze_entry for classification
        outcome = analyze_entry(api_key, st.session_state.journal_entry_text)

    if outcome == "safety":
        st.error("🚨 Your entry contains sensitive content. You're not alone — please talk to someone you trust or contact a professional.")
        st.markdown("""
        * **Samaritans (UK):** Call 116 123 (free, 24/7) or email jo@samaritans.org
        * **Shout (UK):** Text SHOUT to 85258 (free, 24/7 crisis text service)
        * **NHS 111 (UK):** Call 111 for urgent medical advice (non-emergency)
        * **Your local GP or mental health services**
        """)
        st.info("We prioritize your well-being. Please use these resources if you need support.") # Added info message
        st.session_state.ai_initial_response = "" # Ensure no AI journaling response
        set_app_state("entry_submitted") # Transition state to show resources, but not a follow-up form for journaling
    elif outcome == "instruction":
        st.warning("🤔 That looks like an instruction or tech request. Try expressing how you're feeling instead.")
        st.session_state.ai_initial_response = "" # No AI response for instruction
        set_app_state("entry_submitted") # Transition state
    elif outcome == "quiet":
        # For quiet entries, directly trigger the AI call with the crafted structured prompt
        structured_prompt_for_quiet_ai = {
            "task": "encourage_elaboration",
            "user_entry_content": st.session_state.journal_entry_text,
            "original_prompt_context": st.session_state.current_prompt,
            "response_constraints": {
                "max_characters": 150,
                "tone": "empathetic_cheerleader", # Adjusted tone for quiet entries
                "rules": [
                    "Acknowledge the user's entry kindly and empathetically, without false cheer if the content is neutral/negative.",
                    "If the entry is neutral or negative, start with empathy (e.g., 'I hear you,' 'It's okay to feel that way').",
                    "Formulate a single, open-ended question that directly invites the user to explore their personal experience, feelings, or sensory details related to their brief entry.",
                    "The question should encourage elaboration on 'what it was like', 'how it felt', or 'what specific aspect made it impactful' with a sense of gentle wonder.",
                    "Use emojis sparingly and only if truly appropriate for the sentiment of the user's brief entry. Avoid overly enthusiastic emojis for neutral/negative content.",
                    "Do NOT summarize or analyze the user's entry.",
                    "Do NOT ask yes/no questions.",
                    "Keep the question direct, inviting, and focused on personal reflection."
                ]
            }
        }
        get_ai_response_and_set_state(structured_prompt_for_quiet_ai)
    elif outcome == "positive":
        # For positive entries, now also send to AI for a personalized, brief acknowledgment
        structured_prompt_for_positive_ai = {
            "task": "acknowledge_positive_entry",
            "user_entry_content": st.session_state.journal_entry_text,
            "original_prompt_context": st.session_state.current_prompt,
            "response_constraints": {
                "max_characters": 100,
                "tone": "enthusiastic_celebratory", # New tone
                "rules": [
                    "Start with an immediate, high-energy celebration (e.g., 'YES!', 'Awesome!', 'High Five!').",
                    "Acknowledge something specific from the user's entry with genuine excitement.",
                    "Express sincere appreciation in a vibrant way.",
                    "Use exclamation marks and positive emojis (like 🎉, ✨, 🚀).",
                    "Do NOT ask follow-up questions.",
                    "Keep it very brief and impactful (1-2 sentences)."
                ]
            }
        }
        get_ai_response_and_set_state(structured_prompt_for_positive_ai)
        # Mark as concluded since a positive initial entry means no further AI-guided reflection is needed for this chain
        st.session_state.current_reflection_concluded = True


def handle_followup_submission():
    """Handles the submission of the follow-up entry."""
    st.session_state.error_message = "" # Clear previous errors
    if not st.session_state.followup_entry_text.strip():
        st.warning("Please write something for your follow-up.")
        return

    # Ensure reflection is not marked as concluded for a new follow-up submission
    st.session_state.current_reflection_concluded = False

    with st.spinner("Analyzing your follow-up..."):
        # Use AI-powered analyze_entry for classification
        followup_outcome = analyze_entry(api_key, st.session_state.followup_entry_text)

    if followup_outcome == "positive":
        st.success("✨ Excellent! Your reflection is insightful. Thank you for sharing your thoughts.")
        st.session_state.ai_followup_response = "Reflection concluded. Thank you for your deep insights!"
        st.session_state.followup_entry_text = "" # Clear the text area for next potential entry
        st.session_state.error_message = "" # Clear any errors
        st.session_state.current_reflection_concluded = True # Mark as concluded
        set_app_state("entry_submitted") # Revert to entry_submitted state to hide the follow-up form
        st.rerun() # Force rerun to update UI
    elif followup_outcome == "quiet":
        # Still encourage deeper reflection for quiet follow-ups, now using structured input
        structured_prompt_for_quiet_followup_ai = {
            "task": "encourage_elaboration_followup",
            "user_followup_entry_content": st.session_state.followup_entry_text,
            "original_context": {
                "original_prompt": st.session_state.current_prompt,
                "initial_entry": st.session_state.journal_entry_text,
                "initial_ai_response": st.session_state.ai_initial_response
            },
            "response_constraints": {
                "max_characters": 150,
                "tone": "empathetic_cheerleader", # Adjusted tone for quiet entries
                "rules": [
                    "Acknowledge the user's entry kindly and empathetically, without false cheer if the content is neutral/negative.",
                    "If the entry is neutral or negative, start with empathy (e.g., 'I hear you,' 'It's okay to feel that way').",
                    "Formulate a single, open-ended question that directly invites the user to explore their personal experience, feelings, or sensory details related to their brief entry.",
                    "The question should encourage elaboration on 'what it was like', 'how it felt', or 'what specific aspect made it impactful' with a sense of gentle wonder.",
                    "Use emojis sparingly and only if truly appropriate for the sentiment of the user's brief entry. Avoid overly enthusiastic emojis for neutral/negative content.",
                    "Do NOT summarize or analyze the user's entry.",
                    "Do NOT ask yes/no questions.",
                    "Keep the question direct, inviting, and focused on personal reflection."
                ]
            }
        }
        get_ai_response_and_set_state(structured_prompt_for_quiet_followup_ai, is_followup=True)
    elif followup_outcome == "instruction":
        st.warning("🤔 That looks like an instruction or tech request. Try focusing on your thoughts or feelings instead.")
        st.session_state.ai_followup_response = "" # Clear previous AI follow-up if it was an instruction
        st.session_state.followup_entry_text = "" # Clear the text area
        st.session_state.current_reflection_concluded = False # Ensure it's not concluded
        set_app_state("entry_submitted") # Stay in entry_submitted to prompt for new follow-up
        st.rerun() # Force rerun to update UI
    elif followup_outcome == "safety":
        st.error("🚨 Your follow-up contains sensitive content. You're not alone — please talk to someone you trust or contact a professional.")
        st.markdown("""
        * **Samaritans (UK):** Call 116 123 (free, 24/7) or email jo@samaritans.org
        * **Shout (UK):** Text SHOUT to 85258 (free, 24/7 crisis text service)
        * **NHS 111 (UK):** Call 111 for urgent medical advice (non-emergency)
        * **Your local GP or mental health services**
        """)
        st.info("We prioritize your well-being. Please use these resources if you need support.") # Added info message
        st.session_state.ai_followup_response = "" # No AI response for safety
        st.session_state.followup_entry_text = "" # Clear the text area
        st.session_state.current_reflection_concluded = False # Ensure it's not concluded
        set_app_state("entry_submitted") # Stay in entry_submitted to prompt for new follow-up
        st.rerun() # Force rerun to update UI


# --- Main Application UI Layout ---

# Mood selection (always visible)
st.session_state.mood_selected = st.selectbox(
    "How are you feeling today?",
    list(PROMPTS.keys()),
    index=list(PROMPTS.keys()).index(st.session_state.mood_selected) if st.session_state.mood_selected in PROMPTS else 0,
    key="mood_selector",
    on_change=lambda: st.session_state.update(current_prompt=PROMPTS[st.session_state.mood_selected][0],
                                               journal_entry_text="", # Clear entry on mood change
                                               ai_initial_response="",
                                               followup_entry_text="",
                                               ai_followup_response="",
                                               app_state="initial", # Reset state to initial
                                               error_message="")
)
st.markdown(f"### Your prompt: *{st.session_state.current_prompt}*")

# Display general error messages if any
if st.session_state.error_message:
    st.error(st.session_state.error_message)

# --- Conditional UI Rendering based on App State ---

if st.session_state.app_state == "initial":
    # Show initial journal entry form
    with st.form("journal_form"):
        st.session_state.journal_entry_text = st.text_area(
            "Write your response below:",
            value=st.session_state.journal_entry_text,
            height=200,
            key="main_journal_entry"
        )
        submit_button = st.form_submit_button("Submit Entry")
        if submit_button:
            handle_initial_submission()
            # Streamlit will rerun after this function completes, rendering the next state.

elif st.session_state.app_state in ["entry_submitted", "followup_submitted"]:
    # Always display the initial entry and its AI response if available
    if st.session_state.journal_entry_text:
        st.markdown("### Your Initial Entry:")
        st.write(st.session_state.journal_entry_text)
    if st.session_state.ai_initial_response:
        st.markdown("### AI Response (Initial):")
        st.write(st.session_state.ai_initial_response)

    # Display follow-up AI response if available
    if st.session_state.ai_followup_response:
        st.markdown("### AI Response (Follow-Up):")
        st.write(st.session_state.ai_followup_response)

    # Show the follow-up section only if the current reflection chain is NOT concluded
    if not st.session_state.current_reflection_concluded:
        st.markdown("---")
        st.markdown("#### 📝 Let's go deeper?")
        with st.form("followup_form"):
            st.session_state.followup_entry_text = st.text_area(
                "Add a bit more reflection:",
                value=st.session_state.followup_entry_text,
                height=150,
                key="followup_text_area"
            )
            submit_followup_button = st.form_submit_button("Submit More Reflection")
            if submit_followup_button:
                handle_followup_submission()
                # Streamlit will rerun after this, updating the UI based on new state.

st.markdown("---")
# Button to start a new entry (always visible, outside any form)
st.button("🔄 Start New Entry", on_click=reset_app, key="reset_button")
