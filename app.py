import streamlit as st
import os
from utils import classify_and_respond

# --- Streamlit Page Settings ---
st.set_page_config(page_title="Bluum Journal", page_icon="🌸", layout="centered")
st.title("🌸 Bluum Journal")

# --- Session State Initialization ---
if "entry" not in st.session_state:
    st.session_state.entry = ""

if "response" not in st.session_state:
    st.session_state.response = None

if "submitted" not in st.session_state:
    st.session_state.submitted = False

# --- Prompt of the Day ---
current_prompt = "What made you smile today?"
st.markdown(f"#### {current_prompt}")

# --- Text Area Input ---
entry = st.text_area("Your response:", value=st.session_state.entry, height=150)
st.session_state.entry = entry

# --- API Key ---
api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
if not api_key:
    st.warning("Missing API Key. Set OPENROUTER_API_KEY in your environment or Streamlit secrets.")

# --- Submit Logic ---
if st.button("Submit"):
    st.session_state.submitted = True
    st.session_state.response = classify_and_respond(api_key, current_prompt, entry)

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
        st.success(response_text)

# --- Start Over Button ---
if st.button("Start Over"):
    st.session_state.entry = ""
    st.session_state.response = None
    st.session_state.submitted = False
    st.rerun()

