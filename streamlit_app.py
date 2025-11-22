import streamlit as st
st.set_page_config(page_title="🌦️ Rain Forecast Pro (Voice)", layout="wide", page_icon="☔")

import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
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
    tg = "hi" if lang == "Hindi" else "gu"
    try:
        return GoogleTranslator(source="auto", target=tg).translate(text)
    except:
        return text

# ----------------- Header -----------------
st.title(translate_text("🌦️ Rain Forecast Dashboard"))
st.markdown(translate_text("Enter your city name to see past & forecast rainfall, cold/hot extremes, flood risk and farmer advice."))

# ----------------- City Input -----------------
city = st.text_input(translate_text("Enter city name:"), "Ahmedabad")

# ----------------- Open-Meteo Geocoding -----------------
def geocode_city(city_name):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None, None, f"Geocoding error {r.status_code}: {r.text}"
        js = r.json()
        if "results" not in js or len(js["results"]) == 0:
            return None, None, "City not found"
        lat = js["results"][0]["latitude"]
        lon = js["results"][0]["longitude"]
        return lat, lon, None
    except Exception as e:
        return None, None, f"Network error: {e}"

# ----------------- Open-Meteo Forecast -----------------
def fetch_forecast(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        "&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max"
        "&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=12)
        if r.status_code != 200:
            return None, f"Forecast error {r.status_code}: {r.text}"
        return r.json(), None
    except Exception as e:
        return None, f"Network error: {e}"

# ----------------- Build DataFrames -----------------
def build_hourly_df(js):
    hourly = js.get("hourly", {})
    times = hourly.get("time", [])
    rows = []
    for i, t in enumerate(times):
        dt = datetime.fromisoformat(t)
        rows.append({
            "Datetime": dt,
            "Date": dt.date(),
            "Temperature (°C)": hourly["temperature_2m"][i],
            "Humidity (%)": hourly["relative_humidity_2m"][i],
            "Rain (mm)": hourly["precipitation"][i],
            "Wind (km/h)": hourly["wind_speed_10m"][i]
        })
    return pd.DataFrame(rows)

def build_daily_df(js):
    daily = js.get("daily", {})
    rows = []
    for i, t in enumerate(daily.get("time", [])):
        dt = date.fromisoformat(t)
        rows.append({
            "Date": dt,
            "Rain (mm)": daily["precipitation_sum"][i],
            "Temp Max (°C)": daily["temperature_2m_max"][i],
            "Temp Min (°C)": daily["temperature_2m_min"][i],
            "Wind Max (km/h)": daily["wind_speed_10m_max"][i],
        })
    return pd.DataFrame(rows)

# ----------------- Advisory Logic -----------------
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

# ----------------- TTS / STT -----------------
def text_to_speech(text, lang_code):
    if not _have_gtts:
        raise RuntimeError(f"gTTS missing: {_gtts_error}")
    tts = gTTS(text=text, lang=lang_code)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(tmp.name)
    return tmp.name

def transcribe_audio(uploaded_file):
    if not _have_speech_recognition:
        return None, "SpeechRecognition unavailable"
    if not _have_pydub:
        return None, "pydub unavailable"

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as f:
            f.write(uploaded_file.read())
            src = f.name

        audio = AudioSegment.from_file(src)
        wav = src + ".wav"
        audio.export(wav, format="wav")

        recog = sr.Recognizer()
        with sr.AudioFile(wav) as s:
            audio_data = recog.record(s)

        lang_map = {"English": "en-US", "Hindi": "hi-IN", "Gujarati": "gu-IN"}
        text = recog.recognize_google(audio_data, language=lang_map.get(language, "en-US"))
        return text, None
    except Exception as e:
        return None, f"Transcription error: {e}"

# ----------------- MAIN APP -----------------
if city:

    # Geocode
    with st.spinner(translate_text("Finding location...")):
        lat, lon, err = geocode_city(city)
    if err:
        st.error(translate_text("City not found: ") + err)
        st.stop()

    # Forecast
    with st.spinner(translate_text("Fetching forecast...")):
        js, err = fetch_forecast(lat, lon)
    if err:
        st.error(translate_text("Could not fetch forecast: ") + err)
        st.stop()

    df = build_hourly_df(js)
    df_daily = build_daily_df(js)

    if df.empty or df_daily.empty:
        st.error(translate_text("No forecast data available."))
        st.stop()

    # ----------------- Charts -----------------
    st.subheader(translate_text("🕒 Hourly Rain & Temperature"))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name="Rain (mm)", marker_color="skyblue"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"], name="Temperature (°C)", yaxis="y2"))
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="Temperature (°C)"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(translate_text("🌡️ Daily Temperature Range"))
    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(x=df_daily["Date"], y=df_daily["Temp Max (°C)"], name="Hot (°C)", line=dict(color="red")))
    fig_temp.add_trace(go.Scatter(x=df_daily["Date"], y=df_daily["Temp Min (°C)"], name="Cold (°C)", line=dict(color="blue")))
    fig_temp.update_layout(yaxis_title="Temperature (°C)")
    st.plotly_chart(fig_temp, use_container_width=True)

    st.subheader(translate_text("📊 Daily Summary"))
    st.dataframe(df_daily[["Date","Rain (mm)","Temp Min (°C)","Temp Max (°C)","Wind Max (km/h)"]])

    # Flood Risk
    avg_rain = df_daily["Rain (mm)"].mean()
    avg_hum = df["Humidity (%)"].mean()
    if avg_rain > 20 and avg_hum > 80:
        risk, color = translate_text("HIGH — Flood risk"), "red"
    elif avg_rain > 10 and avg_hum > 70:
        risk, color = translate_text("MEDIUM — Watch updates"), "orange"
    else:
        risk, color = translate_text("LOW — No flood risk"), "green"

    st.markdown(f"<div style='padding:10px;border-radius:6px;background:#eef'><b style='color:{color}'>{risk}</b></div>", unsafe_allow_html=True)

    # Farmer Advisory
    st.subheader(translate_text("🤖 RainBot Advisory Assistant"))
    today_rain = df_daily.iloc[0]["Rain (mm)"]
    today_cold = df_daily.iloc[0]["Temp Min (°C)"]
    today_hot = df_daily.iloc[0]["Temp Max (°C)"]
    advice = compose_advice(today_rain, (today_cold+today_hot)/2, avg_hum)
    if today_hot > 40: advice += " ⚠️ High heat alert today — protect crops."
    if today_cold < 10: advice += " ❄️ Cold alert today — protect sensitive crops."
    st.info(translate_text(advice))

    # TTS
    st.subheader(translate_text("🔊 Play Advice"))
    if _have_gtts and st.button(translate_text("Play advice audio")):
        lang_map = {"English": "en", "Hindi": "hi", "Gujarati": "gu"}
        path = text_to_speech(translate_text(advice), lang_map.get(language, "en"))
        st.audio(open(path, "rb").read(), format="audio/mp3")

    # STT
    st.subheader(translate_text("🎤 Ask by Voice (upload audio)"))
    upload = st.file_uploader(translate_text("Upload voice file"), type=["wav","mp3","m4a","ogg"])
    transcribed_text = None
    if upload:
        text, err = transcribe_audio(upload)
        if err: st.error(translate_text(err))
        else:
            st.success(translate_text("Transcription:"))
            st.write(text)
            transcribed_text = text

    # Simple Chat
    st.subheader(translate_text("💬 RainBot Chat"))
    query = st.text_input(translate_text("Ask the Rain bot:"))
    if not query and transcribed_text: query = transcribed_text
    if query:
        q = query.lower()
        if "irrig" in q or "પાણી" in q or "सिंचाई" in q:
            ans = "If rain is expected, delay irrigation."
        elif "fertil" in q or "ખાતર" in q or "खाद" in q:
            ans = "Apply fertilizers on dry days only."
        elif "disease" in q or "રોગ" in q or "रोग" in q:
            ans = "High humidity increases fungal disease risk."
        else:
            ans = "Follow today's advisory and monitor forecast."
        st.success(translate_text(ans))

    # Radar Map (RainViewer)
    st.subheader(translate_text("📡 Weather Radar (RainViewer)"))
    if _have_folium:
        try:
            m = folium.Map(location=[lat, lon], zoom_start=8)
            folium.Marker([lat, lon], popup=city).add_to(m)

            # Add Radar Layer
            rdata = requests.get("https://api.rainviewer.com/public/weather-maps.json").json()
            frames = rdata.get("radar", {}).get("past", [])
            if frames:
                latest = frames[-1]["time"]
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.rainviewer.com/v2/radar/{latest}/{{z}}/{{x}}/{{y}}.png",
                    attr="RainViewer",
                    name="Radar",
                    opacity=0.6
                ).add_to(m)

            st_folium(m, width=700, height=400)
        except Exception:
            st.warning("Map failed to load. Showing simple map.")
            st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))
    else:
        st.info("Install Folium to enable radar maps.")
