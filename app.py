# app.py
import streamlit as st
import json
import os
from utils import analyze_entry, get_journal_response, check_flag

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Bluum Journal", layout="centered")
st.title("🪴 Bluum Daily Reflection")

# --- Constants and File Loading ---
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "prompts.json")
SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "system_prompt.txt")

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
        "followup_entry_text", "ai_followup_response", "error_message"
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
    st.rerun() # Force a rerun to clear the UI

def get_ai_response_and_set_state(user_input_for_ai: str, is_followup: bool = False):
    """
    Fetches AI response and updates the appropriate session state variable.
    Handles general AI responses and follow-up responses.
    The `user_input_for_ai` is the content that goes into the 'user' role of the API call.
    """
    st.session_state.error_message = "" # Clear previous errors
    response_target_key = "ai_followup_response" if is_followup else "ai_initial_response"
    
    with st.spinner("Generating response..."):
        # For follow-up, provide full context in the user message
        if is_followup:
            full_context_user_message = (
                f"Original Prompt: {st.session_state.current_prompt}\n"
                f"Original Entry: {st.session_state.journal_entry_text}\n"
                f"Follow-up Reflection: {user_input_for_ai}" # user_input_for_ai is the actual followup text here
            )
            response = get_journal_response(api_key, SYSTEM_PROMPT, full_context_user_message)
        else:
            # For initial entries (including 'quiet' where user_input_for_ai is a crafted prompt)
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

    outcome = analyze_entry(st.session_state.journal_entry_text)

    if outcome == "safety":
        with st.spinner("Checking for safety concerns..."):
            ai_check = check_flag(
                api_key,
                "Does this sound like a mental health crisis? Reply 'yes' or 'no'.",
                st.session_state.journal_entry_text
            )
        if ai_check and "yes" in ai_check.lower():
            st.error("🚨 You're not alone — please talk to someone you trust or contact a professional. Here are some resources:")
            st.markdown("""
            * **Samaritans (UK):** Call 116 123 (free, 24/7) or email jo@samaritans.org
            * **Shout (UK):** Text SHOUT to 85258 (free, 24/7 crisis text service)
            * **NHS 111 (UK):** Call 111 for urgent medical advice (non-emergency)
            * **Your local GP or mental health services**
            """)
            st.session_state.ai_initial_response = "" # No AI response for safety
            set_app_state("entry_submitted") # Show resources, but don't proceed to follow-up directly with AI
        else:
            st.info("🫂 That sounded intense, but we can keep journaling. Here's what I think:")
            # Use the actual journal entry for AI processing
            get_ai_response_and_set_state(st.session_state.journal_entry_text)
    elif outcome == "instruction":
        with st.spinner("Analyzing entry type..."):
            ai_check = check_flag(
                api_key,
                "Is this a journaling entry or an instruction/technical prompt? Reply with 'journal' or 'instruction'.",
                st.session_state.journal_entry_text
            )
        if ai_check and "instruction" in ai_check.lower():
            st.warning("🤔 That looks like an instruction or tech request. Try expressing how you're feeling instead.")
            st.session_state.ai_initial_response = "" # No AI response for instruction
        else:
            # Use the actual journal entry for AI processing
            get_ai_response_and_set_state(st.session_state.journal_entry_text)
        set_app_state("entry_submitted") # Always transition after initial check/response
    elif outcome == "quiet":
        # For quiet entries, directly trigger the AI call with the crafted prompt
        # No need for an intermediate st.info message here, the AI response will be the primary feedback.
        prompt_for_quiet_ai = (
            f"The user's journal entry was very short: '{st.session_state.journal_entry_text}'. "
            f"Your original prompt was: '{st.session_state.current_prompt}'. "
            "Please provide a gentle, encouraging response that helps the user elaborate or delve deeper into their initial thought. "
            "Do NOT summarize or analyze, just prompt for more detail. Focus on encouraging them to expand on their brief entry."
        )
        # Pass this crafted prompt as the user_input_for_ai
        get_ai_response_and_set_state(prompt_for_quiet_ai)
        # The state will be set to 'entry_submitted' within get_ai_response_and_set_state upon success, followed by rerun.
    elif outcome == "positive":
        # For positive entries, just display a thank you message, no AI call needed
        st.success("🎉 Thank you for sharing your thoughts! We appreciate your positive reflection.")
        st.session_state.ai_initial_response = "Thank you for sharing your thoughts! We appreciate your positive reflection."
        set_app_state("entry_submitted")
        st.rerun() # Force a rerun to display the thank you message immediately


def handle_followup_submission():
    """Handles the submission of the follow-up entry."""
    st.session_state.error_message = "" # Clear previous errors
    if not st.session_state.followup_entry_text.strip():
        st.warning("Please write something for your follow-up.")
        return

    followup_outcome = analyze_entry(st.session_state.followup_entry_text)

    if followup_outcome == "positive":
        st.success("✨ Excellent! Your reflection is insightful. Thank you for sharing your thoughts.")
        st.session_state.ai_followup_response = "Reflection concluded. Thank you for your deep insights!" # A concluding message
        st.session_state.followup_entry_text = "" # Clear the text area for next potential entry
        st.session_state.error_message = "" # Clear any errors
        set_app_state("entry_submitted") # Revert to entry_submitted state to hide the follow-up form
        st.rerun() # Force rerun to update UI
    elif followup_outcome == "quiet":
        # Still encourage deeper reflection for quiet follow-ups
        prompt_for_quiet_followup_ai = (
            f"The user's follow-up reflection was very short: '{st.session_state.followup_entry_text}'. "
            f"Original Prompt: {st.session_state.current_prompt}\n"
            f"Original Entry: {st.session_state.journal_entry_text}\n"
            "Please provide a gentle, encouraging response that helps the user elaborate or delve deeper into their follow-up thought. "
            "Do NOT summarize or analyze, just prompt for more detail. Focus on encouraging them to expand on their brief entry."
        )
        get_ai_response_and_set_state(prompt_for_quiet_followup_ai, is_followup=True)
    elif followup_outcome == "instruction":
        st.warning("🤔 That looks like an instruction or tech request. Try focusing on your thoughts or feelings rather than giving an instruction for your follow-up.")
        st.session_state.ai_followup_response = "" # Clear previous AI follow-up if it was an instruction
        st.session_state.followup_entry_text = "" # Clear the text area
        set_app_state("entry_submitted") # Stay in entry_submitted to prompt for new follow-up
        st.rerun() # Force rerun to update UI
    elif followup_outcome == "safety":
        st.error("🚨 Your follow-up sounds concerning. You're not alone — please talk to someone you trust or contact a professional. Here are some resources:")
        st.markdown("""
        * **Samaritans (UK):** Call 116 123 (free, 24/7) or email jo@samaritans.org
        * **Shout (UK):** Text SHOUT to 85258 (free, 24/7 crisis text service)
        * **NHS 111 (UK):** Call 111 for urgent medical advice (non-emergency)
        * **Your local GP or mental health services**
        """)
        st.session_state.ai_followup_response = "" # No AI response for safety
        st.session_state.followup_entry_text = "" # Clear the text area
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
    # A reflection chain is concluded if:
    # 1. The initial response was the "Thank you..." message (for positive initial entries).
    # 2. The follow-up response is the "Reflection concluded..." message (for positive follow-up entries).
    reflection_concluded = (
        st.session_state.ai_initial_response == "Thank you for sharing your thoughts! We appreciate your positive reflection." or
        st.session_state.ai_followup_response == "Reflection concluded. Thank you for your deep insights!"
    )

    if not reflection_concluded:
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

