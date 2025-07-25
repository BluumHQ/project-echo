# app.py
import streamlit as st
import json
import os
from utils import analyze_entry, get_journal_response
from typing import Union

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Bluum Journal", layout="centered")
st.title("🪴 Bluum Daily Reflection")

# --- Load Prompts and System Prompt ---
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "prompts.json")
SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "system_prompt.txt")

try:
    with open(PROMPTS_FILE, "r") as f:
        PROMPTS = json.load(f)
except FileNotFoundError:
    st.error(f"Error: {PROMPTS_FILE} not found.")
    st.stop()

try:
    with open(SYSTEM_PROMPT_FILE, "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    st.error(f"Error: {SYSTEM_PROMPT_FILE} not found.")
    st.stop()

# --- API Key ---
api_key = st.secrets.get("OPENROUTER_API_KEY")
if not api_key:
    st.warning("Please set your OpenRouter API key in secrets.toml.")
    st.stop()

# --- Session State ---
if "mood" not in st.session_state:
    st.session_state.mood = list(PROMPTS.keys())[0]
if "entry" not in st.session_state:
    st.session_state.entry = ""
if "ai_response" not in st.session_state:
    st.session_state.ai_response = ""
if "submitted" not in st.session_state:
    st.session_state.submitted = False

# --- Mood Selection ---
st.session_state.mood = st.selectbox("How are you feeling today?", list(PROMPTS.keys()),
                                     index=list(PROMPTS.keys()).index(st.session_state.mood))
current_prompt = PROMPTS[st.session_state.mood][0]
st.markdown(f"### Your prompt: *{current_prompt}*")

# --- Entry Form ---
with st.form("entry_form"):
    st.session_state.entry = st.text_area("Reflect on your day:", value=st.session_state.entry, height=200)
    submitted = st.form_submit_button("Submit")
    if submitted:
        st.session_state.submitted = True

# --- Handle Submission ---
if st.session_state.submitted:
    outcome = analyze_entry(api_key, st.session_state.entry)

    if outcome == "safety":
        st.error("🚨 You mentioned something serious. Please reach out to someone you trust or contact a professional.")
        st.markdown("""
        **Resources:**
        - Samaritans (UK): 116 123
        - Shout (UK): Text SHOUT to 85258
        - NHS 111: Call 111
        """)
    elif outcome == "instruction":
        st.warning("🤔 That looks like a command or tech question. Try journaling about your day instead.")
    elif outcome in ["quiet", "positive"]:
        relevance_prompt = {
            "task": "acknowledge_and_check_relevance" if outcome == "positive" else "encourage_elaboration_and_check_relevance",
            "user_entry_content": st.session_state.entry,
            "original_prompt_context": current_prompt,
            "response_constraints": {
                "max_characters": 150 if outcome == "quiet" else 100,
                "tone": "empathetic_cheerleader" if outcome == "quiet" else "enthusiastic_celebratory",
                "rules": [
                    "Your output MUST be a JSON object with 'relevance' and 'response_text'.",
                    "If 'not_relevant', gently nudge back to the prompt theme.",
                    "If 'relevant', acknowledge kindly and respond accordingly."
                ]
            }
        }
        with st.spinner("Thinking..."):
            response_text = get_journal_response(api_key, SYSTEM_PROMPT, relevance_prompt)

        if response_text:
            try:
                parsed = json.loads(response_text.strip("` "))
                if parsed.get("relevance") == "not_relevant":
                    st.info(parsed.get("response_text", "Let's try to reflect a bit more on the prompt."))
                else:
                    st.success(parsed.get("response_text", "Thanks for sharing!"))
            except json.JSONDecodeError:
                st.info("Hmm, I couldn't understand that. Try rephrasing your reflection.")
        else:
            st.warning("There was an issue getting a response. Please try again later.")
    else:
        st.info("Not quite sure what that was. Try reflecting a bit more deeply.")

    st.session_state.submitted = False

st.markdown("---")
st.button("Start Over", on_click=lambda: st.session_state.update(entry="", ai_response="", submitted=False))
