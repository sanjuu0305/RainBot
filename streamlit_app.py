# farmer_advisor_voice.py

import streamlit as st
st.set_page_config(page_title="🌦️ Rain Forecast Pro (Voice)", layout="wide", page_icon="☔")

import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from deep_translator import GoogleTranslator
import tempfile
import os

# ----------------- Optional Voice Libraries -----------------
_have_gtts = False
_have_speech_recognition = False
_have_pydub = False
_gtts_error = None
_sr_error = None
_pydub_error = None

try:
    from gtts import gTTS
    _have_gtts = True
except Exception as e:
    _gtts_error = e

try:
    import speech_recognition as sr
    _have_speech_recognition = True
except Exception as e:
    _sr_error = e

try:
    from pydub import AudioSegment
    _have_pydub = True
except Exception as e:
    _pydub_error = e

# ----------------- Optional Folium Maps -----------------
_have_folium = False
_folium_import_error = None
try:
    import folium
    from streamlit_folium import st_folium
    _have_folium = True
except Exception as e:
    _folium_import_error = e

# ----------------- Sidebar Language Selector -----------------
st.sidebar.header("🌐 Choose language / ભાષા પસંદ કરો")
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])

def translate_text(text, lang=None):
    if lang is None:
        lang = language
    if lang == "English":
        return text
    target = "hi" if lang == "Hindi" else "gu"
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        return text

# ----------------- Header -----------------
st.title(translate_text("🌦️ Rain Forecast Dashboard"))
st.markdown(translate_text("Enter your city name to see past & forecast rainfall, flood risk and farmer advice."))

# ----------------- API Key -----------------
api_key = st.secrets.get("openweather_api_key", "")
if not api_key:
    st.error(translate_text("API key missing. Add 'openweather_api_key' in Streamlit Secrets."))
    st.stop()

# ----------------- Input -----------------
city = st.text_input(translate_text("Enter city name:"), "Ahmedabad")

# ----------------- Geocoding -----------------
def geocode_city(city_name):
    geo_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city_name, "limit": 1, "appid": api_key}
    try:
        r = requests.get(geo_url, params=params, timeout=10)
        if r.status_code != 200:
            return None, None, f"Geocoding API error {r.status_code}: {r.text}"
        data = r.json()
        if not data:
            return None, None, "No geocoding result"
        return data[0]["lat"], data[0]["lon"], None
    except Exception as e:
        return None, None, f"Network/geocode error: {e}"

# ----------------- Forecast API -----------------
def fetch_forecast_by_latlon(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, f"Forecast API error {r.status_code}: {r.text}"
        return r.json(), None
    except Exception as e:
        return None, f"Network/forecast error: {e}"

# ----------------- Build Forecast DataFrame -----------------
def build_forecast_df(forecast_json):
    items = forecast_json.get("list", [])
    rows = []
    for it in items:
        dt = datetime.fromtimestamp(it.get("dt", 0))
        rows.append({
            "Datetime": dt,
            "Date": dt.date(),
            "Temperature (°C)": it.get("main", {}).get("temp"),
            "Humidity (%)": it.get("main", {}).get("humidity"),
            "Rain (mm)": it.get("rain", {}).get("3h", 0.0),
            "Condition": it.get("weather", [{}])[0].get("description", "").capitalize(),
            "Wind (km/h)": round(it.get("wind", {}).get("speed", 0.0) * 3.6, 1)
        })
    return pd.DataFrame(rows)

# ----------------- Farmer Advice Logic -----------------
def compose_advice(today_rain, avg_temp, avg_hum):
    if today_rain > 30:
        advice = "Heavy rain expected — avoid fertilizer application, secure harvested crops, and ensure drainage."
    elif today_rain > 10:
        advice = "Moderate rain expected — delay irrigation and spraying; prepare drainage."
    elif today_rain > 0:
        advice = "Light rain expected — minimal irrigation needed."
    else:
        advice = "No rain expected — schedule irrigation and fertilizer application on dry day."

    if avg_temp:
        if avg_temp > 35:
            advice += " High temperatures — apply mulch and irrigate during cooler hours."
        elif avg_temp < 20:
            advice += " Cooler weather — suitable for sowing wheat and mustard."

    if avg_hum and avg_hum > 85:
        advice += " High humidity — monitor for fungal diseases."

    return advice

# ----------------- Text-To-Speech -----------------
def text_to_speech(text, lang_code):
    if not _have_gtts:
        raise RuntimeError(f"gTTS not available: {_gtts_error}")
    tts = gTTS(text=text, lang=lang_code)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(tmp.name)
    return tmp.name

# ----------------- Speech-To-Text -----------------
def transcribe_audio(uploaded_file):
    if not _have_speech_recognition:
        return None, f"SpeechRecognition not available: {_sr_error}"
    if not _have_pydub:
        return None, f"Pydub not available: {_pydub_error}"

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as f:
            f.write(uploaded_file.read())
            src_path = f.name
    except:
        return None, "File save error"

    try:
        audio = AudioSegment.from_file(src_path)
        wav_path = src_path + ".wav"
        audio.export(wav_path, format="wav")
    except Exception as e:
        return None, f"Audio conversion failed: {e}"

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        lang_map = {"English":"en-US","Hindi":"hi-IN","Gujarati":"gu-IN"}
        text = recognizer.recognize_google(audio_data, language=lang_map.get(language, "en-US"))
        return text, None
    except Exception as e:
        return None, f"Transcription error: {e}"
    finally:
        try:
            os.remove(src_path)
            os.remove(wav_path)
        except:
            pass

# -------------------------------------------------------
#                      MAIN APP
# -------------------------------------------------------

if city:
    # ---- Geocode ----
    with st.spinner(translate_text("Finding location...")):
        lat, lon, geo_err = geocode_city(city)
    if geo_err:
        st.error(translate_text("City not found: ") + geo_err)
        st.stop()

    # ---- Forecast ----
    with st.spinner(translate_text("Fetching forecast...")):
        forecast_json, forecast_err = fetch_forecast_by_latlon(lat, lon)
    if forecast_err:
        st.error(translate_text("Could not fetch forecast: ") + forecast_err)
        st.stop()

    df = build_forecast_df(forecast_json)
    if df.empty:
        st.error(translate_text("No forecast data found."))
        st.stop()

    # ----------------- Charts -----------------
    st.subheader(translate_text("🕒 Hourly Rain & Temperature"))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name="Rain (mm)", marker_color="skyblue"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"],
                             name="Temperature (°C)", yaxis="y2"))
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", title="Temperature (°C)")
    )
    st.plotly_chart(fig, use_container_width=True)

    # ----------------- Daily Summary -----------------
    st.subheader(translate_text("📊 Daily Rain Summary"))
    df_daily = df.groupby("Date").agg({"Rain (mm)": "sum", 
                                       "Temperature (°C)": "mean", 
                                       "Humidity (%)": "mean"}).reset_index()
    st.dataframe(df_daily)

    # ----------------- Flood Risk -----------------
    avg_rain = df_daily["Rain (mm)"].mean()
    avg_hum = df_daily["Humidity (%)"].mean()

    if avg_rain > 20 and avg_hum > 80:
        flood_text, color = translate_text("HIGH — Flood risk possible"), "red"
    elif avg_rain > 10 and avg_hum > 70:
        flood_text, color = translate_text("MEDIUM — Watch updates"), "orange"
    else:
        flood_text, color = translate_text("LOW — No flood risk"), "green"

    st.markdown(f"<div style='padding:10px;border-radius:6px;background-color:#eef'><b style='color:{color}'>{flood_text}</b></div>", unsafe_allow_html=True)

    # ----------------- Farmer Advisory -----------------
    st.subheader(translate_text("🤖 Farmer Advisory Assistant"))
    today_rain = df_daily.iloc[0]["Rain (mm)"]
    advice = compose_advice(today_rain, df_daily["Temperature (°C)"].mean(), avg_hum)
    st.info(translate_text(advice))

    # ----------------- TTS -----------------
    st.subheader(translate_text("🔊 Play Advice"))
    if _have_gtts:
        if st.button(translate_text("Play advice audio")):
            lang_map = {"English": "en", "Hindi": "hi", "Gujarati": "gu"}
            path = text_to_speech(translate_text(advice), lang_map.get(language, "en"))
            st.audio(open(path, "rb").read(), format="audio/mp3")
    else:
        st.warning("gTTS unavailable")

    # ----------------- STT -----------------
    st.subheader(translate_text("🎤 Ask by Voice (upload audio)"))
    upload = st.file_uploader(translate_text("Upload voice file"), type=["wav","mp3","m4a","ogg"])
    transcribed_text = None
    if upload:
        text, err = transcribe_audio(upload)
        if err:
            st.error(translate_text(err))
        else:
            st.success(translate_text("Transcription:"))
            st.write(text)
            transcribed_text = text

    # ----------------- Chat -----------------
    st.subheader(translate_text("💬 Farmer Chat"))
    user_q = st.text_input(translate_text("Ask the farmer bot:"))
    if not user_q and transcribed_text:
        user_q = transcribed_text

    if user_q:
        q = user_q.lower()
        if any(x in q for x in ["irrigate", "water", "પાણી", "सिंचाई"]):
            reply = "If rain is expected, delay irrigation."
        elif any(x in q for x in ["fertilizer", "ખાતર", "खाद"]):
            reply = "Apply fertilizers only on dry days."
        elif any(x in q for x in ["disease", "રોગ", "रोग"]):
            reply = "High humidity increases disease risk."
        elif any(x in q for x in ["harvest", "કાપણી", "कटाई"]):
            reply = "Harvest only on dry days."
        else:
            reply = "Follow today's advisory and check tomorrow’s forecast."
        st.success(translate_text(reply))

    # ----------------- Maps -----------------
    st.subheader(translate_text("📡 Weather Radar"))
    if _have_folium:
        try:
            m = folium.Map(location=[lat, lon], zoom_start=8)
            folium.Marker([lat, lon], popup=city).add_to(m)
            st_folium(m, width=700, height=400)
        except Exception as e:
            st.warning("Map failed")
            st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))
    else:
        st.info("Install Folium for maps.")

