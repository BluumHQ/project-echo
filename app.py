import streamlit as st
import os
import uuid
import logging
import subprocess

from utils import classify_and_respond, get_version_info, MOOD_CHOICES

logging.basicConfig(level=logging.INFO)

# --- Streamlit Page Settings ---
st.set_page_config(page_title="Bluum Journal", page_icon="🌸", layout="centered")
st.title("🌸 Bluum Journal")

# --- Reset Session State ---
if "reset" in st.session_state and st.session_state.reset:
    for key in ["entry", "response", "prompts", "conversation", "submitted"]:
        st.session_state.pop(key, None)
    st.session_state.reset = False
    st.session_state.mood = "OK"
    st.rerun() # Reset the session state if requested

# --- Session State Initialization ---

if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "conversation" not in st.session_state:
    st.session_state.conversation = {}

if "prompts" not in st.session_state:
    st.session_state.prompts = []

if "response" not in st.session_state:
    st.session_state.response = None

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "entry" not in st.session_state:
    st.session_state.entry = ""

if "mood" not in st.session_state:
    st.session_state.mood = "OK"

def smile_response_callback():
    st.session_state.prompts.append(current_prompt.strip())
    prompt_index = len(st.session_state.prompts) - 1
    st.session_state.conversation[prompt_index] = st.session_state.entry.strip()

# --- Mood selection
mood_choice = st.select_slider(
    "How do you feel today?",
    options=MOOD_CHOICES, key="mood",
)
st.write("Your're feeling... ", mood_choice)

# --- Prompt of the Day ---
current_prompt = "What made you smile today?"
st.markdown(f"#### {current_prompt}")

# --- Text Area Input ---
st.text_area("Your response:", key="entry", height=150, on_change=smile_response_callback)

# --- API Key ---
api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
if not api_key:
    st.warning("Missing API Key. Set OPENROUTER_API_KEY in your environment or Streamlit secrets.")

# --- Submit Logic ---
if st.button("Submit"):
    st.session_state.submitted = True
    st.session_state.response = classify_and_respond(api_key, st.session_state.session_id, st.session_state.prompts, st.session_state.conversation, mood_choice)

# --- Display Response ---
if st.session_state.submitted and st.session_state.response:
    category = st.session_state.response.get("category")
    response_text = st.session_state.response.get("response_text", "").strip()

    if category == "safety":
        st.error(response_text)
        st.info("If you're struggling, please reach out to someone you trust or seek professional help.")
    elif category == "unclear" and not response_text:
        st.warning("Hmm, we couldn't quite understand that. Try again?")
    else:
        current_prompt = response_text
        st.success(response_text)

# --- Start Over Button ---
if st.button("Start Over"):
    st.session_state.reset = True
    st.rerun()  # Reset the session state and rerun the app

# Print versions info at the bottom for reference
get_version_info(st.session_state.session_id)