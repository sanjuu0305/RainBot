import streamlit as st
from utils import text_to_speech, transcribe_audio, compose_advice

st.set_page_config(page_title="Voice Chat", layout="wide", page_icon="🎤")
st.title("🎤 Voice Chat with Farmer Bot")

language = st.sidebar.selectbox("Language", ["English","Hindi","Gujarati"])
crop = st.sidebar.selectbox("Select Crop", ["None","Wheat","Rice","Maize"])

# Upload voice
uploaded_audio = st.file_uploader("Upload audio (wav/mp3/m4a)", type=["wav","mp3","m4a"])
if uploaded_audio:
    text, err = transcribe_audio(uploaded_audio, language)
    if err: st.error(err)
    else:
        st.success(f"Transcribed Text: {text}")
        # Generate advice based on transcription
        user_q = text.lower()
        advice_text = ""
        if "irrigate" in user_q or "water" in user_q: advice_text = "Delay irrigation if rain expected; otherwise water early morning."
        elif "fertilizer" in user_q: advice_text = "Apply fertilizer on dry days; avoid heavy rain."
        elif "disease" in user_q: advice_text = "Monitor crops for fungal disease; apply protection if high humidity."
        elif "harvest" in user_q: advice_text = "Harvest on dry days; avoid rain periods."
        else: advice_text = "Weather looks moderate. Follow general advisory."

        st.info(advice_text)
        if st.button("Play advice audio"):
            try:
                mp3 = text_to_speech(advice_text, lang_code={"English":"en","Hindi":"hi","Gujarati":"gu"}.get(language,"en"))
                with open(mp3,"rb") as f: st.audio(f.read(), format="audio/mp3")
            except Exception as e: st.error(f"TTS error: {e}")
