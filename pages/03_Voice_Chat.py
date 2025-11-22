import streamlit as st
from utils import text_to_speech, transcribe_audio

st.set_page_config(page_title="Voice Chat", layout="wide", page_icon="🎤")
st.title("🎤 Voice Chat with Farmer Bot")

# ---------------- Sidebar ----------------
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])
crop = st.sidebar.selectbox("Select Crop", ["None", "Wheat", "Rice", "Maize"])

# ---------------- Upload Audio ----------------
uploaded_audio = st.file_uploader("Upload audio (wav/mp3/m4a)", type=["wav","mp3","m4a"])

if uploaded_audio:
    # Transcribe audio
    text, err = transcribe_audio(uploaded_audio, language)
    if err:
        st.error(err)
    else:
        st.success(f"Transcribed Text: {text}")

        # ---------------- Generate Advice ----------------
        user_q = text.lower()
        advice_text = ""

        if any(word in user_q for word in ["irrigate", "water", "પાણી", "सिंचाई"]):
            advice_text = "Delay irrigation if rain is expected; otherwise, water early morning."
        elif any(word in user_q for word in ["fertilizer", "ખાતર", "खाद"]):
            advice_text = "Apply fertilizer on dry days; avoid heavy rain."
        elif any(word in user_q for word in ["disease", "રોગ", "रोग"]):
            advice_text = "Monitor crops for fungal disease; apply protection if high humidity."
        elif any(word in user_q for word in ["harvest", "કાપણી", "कटाई"]):
            advice_text = "Harvest on dry days; avoid rain periods."
        else:
            advice_text = "Weather looks moderate. Follow general advisory."

        st.info(advice_text)

        # ---------------- Text-to-Speech ----------------
        if st.button("🔊 Play Advice Audio"):
            try:
                lang_map = {"English": "en", "Hindi": "hi", "Gujarati": "gu"}
                mp3_path = text_to_speech(advice_text, lang_code=lang_map.get(language, "en"))
                with open(mp3_path, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
            except Exception as e:
                st.error(f"TTS error: {e}")
