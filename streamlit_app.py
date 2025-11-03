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

# Voice libraries (optional)
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

# Optional folium imports
_have_folium = False
_folium_import_error = None
try:
    import folium
    from streamlit_folium import st_folium
    _have_folium = True
except Exception as e:
    _folium_import_error = e

# ----------------- Sidebar: Language Selector -----------------
st.sidebar.header("🌐 Choose language / ભાષા પસંદ કરો")
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])

def translate_text(text, lang=None):
    """Translate UI text with deep-translator"""
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

# ----------------- API key (use secrets) -----------------
api_key = st.secrets.get("openweather_api_key", "")
if not api_key:
    st.error(translate_text("API key missing. Add 'openweather_api_key' in Streamlit Secrets."))
    st.info('Example (Streamlit Secrets):\n\nopenweather_api_key = "your_openweathermap_api_key_here"')
    st.stop()

# ----------------- Input -----------------
city = st.text_input(translate_text("Enter city name:"), "Ahmedabad")

# ----------------- Geocoding using OpenWeatherMap -----------------
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
        lat = data[0]["lat"]
        lon = data[0]["lon"]
        return lat, lon, None
    except requests.exceptions.RequestException as e:
        return None, None, f"Network/geocode error: {e}"

# ----------------- Fetch forecast data -----------------
def fetch_forecast_by_latlon(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, f"Forecast API error {r.status_code}: {r.text}"
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Network/forecast error: {e}"

# ----------------- Helper to build DataFrame -----------------
def build_forecast_df(forecast_json):
    items = forecast_json.get("list", [])
    rows = []
    for it in items:
        dt = datetime.fromtimestamp(it.get("dt", 0))
        temp = it.get("main", {}).get("temp")
        hum = it.get("main", {}).get("humidity")
        rain = it.get("rain", {}).get("3h", 0.0) if it.get("rain") else 0.0
        cond = it.get("weather", [{}])[0].get("description", "").capitalize()
        wind = round(it.get("wind", {}).get("speed", 0.0) * 3.6, 1)
        rows.append({"Datetime": dt, "Date": dt.date(), "Temperature (°C)": temp,
                     "Humidity (%)": hum, "Rain (mm)": rain, "Condition": cond, "Wind (km/h)": wind})
    df = pd.DataFrame(rows)
    return df

# ----------------- Simple Advisory Logic -----------------
def compose_advice(today_rain, avg_temp, avg_hum):
    # Base advice
    if today_rain > 30:
        advice = "Heavy rain expected — avoid fertilizer application, secure harvested crops and livestock, and ensure drainage is clear."
    elif today_rain > 10:
        advice = "Moderate rain expected — delay irrigation and spraying; prepare drainage."
    elif today_rain > 0:
        advice = "Light rain expected — minimal irrigation needed; cover sensitive crops if forecast shows heavier rain later."
    else:
        advice = "No rain expected — schedule irrigation and fertilizer application on dry day."

    # Temperature-related tips
    if avg_temp is not None:
        if avg_temp > 35:
            advice += " High temperatures — apply mulch and irrigate during cooler hours."
        elif avg_temp < 20:
            advice += " Cooler weather — suitable for sowing wheat and mustard."

    # Humidity disease risk
    if avg_hum is not None and avg_hum > 85:
        advice += " High humidity — monitor for fungal diseases and consider protective treatments."

    return advice

# ----------------- TTS helper (gTTS) -----------------
def text_to_speech(text, lang_code):
    """
    Create an MP3 in a temp file using gTTS and return the file path.
    lang_code: 'en', 'hi', 'gu' (gTTS uses 'gu' for Gujarati if available)
    """
    if not _have_gtts:
        raise RuntimeError(f"gTTS not available: {_gtts_error}")
    tts = gTTS(text=text, lang=lang_code)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    tts.save(tmp_name)
    return tmp_name

# ----------------- STT helper (upload + transcription) -----------------
def transcribe_audio(uploaded_file):
    """
    Accepts an uploaded audio file (bytes), converts to WAV if needed (pydub),
    and uses SpeechRecognition to transcribe.
    Returns transcribed text or error message.
    """
    if not _have_speech_recognition:
        return None, f"SpeechRecognition not available: {_sr_error}"
    if not _have_pydub:
        return None, f"Pydub not available: {_pydub_error}"

    # Save uploaded to temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as f:
            f.write(uploaded_file.read())
            src_path = f.name
    except Exception as e:
        return None, f"Failed to save upload: {e}"

    # Convert to WAV if necessary
    try:
        audio = AudioSegment.from_file(src_path)
        wav_path = src_path + ".wav"
        audio.export(wav_path, format="wav")
    except Exception as e:
        return None, f"Audio conversion failed (ffmpeg needed): {e}"

    # Recognize
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        # Choose language for recognition
        sr_lang = "en-US"
        if language == "Hindi":
            sr_lang = "hi-IN"
        elif language == "Gujarati":
            sr_lang = "gu-IN"
        text = recognizer.recognize_google(audio_data, language=sr_lang)
        return text, None
    except Exception as e:
        return None, f"Transcription error: {e}"
    finally:
        # cleanup
        try:
            os.remove(src_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass

# ----------------- Main flow -----------------
if city:
    with st.spinner(translate_text("Finding location...")):
        lat, lon, geo_err = geocode_city(city)
    if geo_err:
        st.error(translate_text("City not found or geocode failed: ") + f" {geo_err}")
        st.stop()

    with st.spinner(translate_text("Fetching forecast...")):
        forecast_json, forecast_err = fetch_forecast_by_latlon(lat, lon)
    if forecast_err:
        st.error(translate_text("Could not fetch forecast: ") + f"{forecast_err}")
        st.stop()

    df = build_forecast_df(forecast_json)
    if df.empty:
        st.error(translate_text("No forecast data available."))
        st.stop()

    # Hourly chart
    st.subheader(translate_text("🕒 Hourly Rain & Temperature (3-hour steps)"))
    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name=translate_text("Rain (mm)"), marker_color="skyblue"))
    fig_h.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"], name=translate_text("Temperature (°C)"),
                               mode="lines+markers", yaxis="y2"))
    fig_h.update_layout(title=translate_text("Hourly Rain & Temperature"),
                        xaxis_title=translate_text("Time"),
                        yaxis=dict(title=translate_text("Rain (mm)")),
                        yaxis2=dict(title=translate_text("Temperature (°C)"), overlaying="y", side="right"))
    st.plotly_chart(fig_h, use_container_width=True)

    # Daily summary
    st.subheader(translate_text("📊 Daily Rain Summary"))
    df_daily = df.groupby("Date").agg({
        "Rain (mm)": "sum",
        "Temperature (°C)": "mean",
        "Humidity (%)": "mean"
    }).reset_index().sort_values("Date")
    st.dataframe(df_daily, use_container_width=True)

    # Flood risk
    st.subheader(translate_text("💧 Flood Risk Index"))
    avg_rain = float(df_daily["Rain (mm)"].mean()) if not df_daily.empty else 0.0
    avg_hum = float(df_daily["Humidity (%)"].mean()) if not df_daily.empty else 0.0
    if avg_rain > 20 and avg_hum > 80:
        flood_text = translate_text("HIGH — Flood risk possible"); color = "red"
    elif avg_rain > 10 and avg_hum > 70:
        flood_text = translate_text("MEDIUM — Watch updates"); color = "orange"
    else:
        flood_text = translate_text("LOW — No flood risk"); color = "green"
    st.markdown(f"<div style='padding:10px;border-radius:6px;background-color:#f7fbff'><b style='color:{color}'>{flood_text}</b></div>", unsafe_allow_html=True)

    # ----------------- Farmer Advisory -----------------
    st.subheader(translate_text("🤖 Farmer Advisory Assistant"))
    today_rain = float(df_daily.iloc[0]["Rain (mm)"]) if not df_daily.empty else 0.0
    avg_temp = float(df_daily["Temperature (°C)"].mean()) if not df_daily.empty else None
    avg_hum = float(df_daily["Humidity (%)"].mean()) if not df_daily.empty else None

    advice_text = compose_advice(today_rain, avg_temp, avg_hum)
    st.info(translate_text(advice_text))

    # ----------------- Voice: TTS playback of advice -----------------
    st.subheader(translate_text("🔊 Play Advice (Voice)"))
    if not _have_gtts:
        st.warning("TTS (gTTS) not available. Install 'gTTS' to enable voice playback.")
        if _gtts_error:
            st.write(f"gTTS error: {_gtts_error}")
    else:
        # map language to gTTS language codes
        lang_map = {"English": "en", "Hindi": "hi", "Gujarati": "gu"}
        gtts_lang = lang_map.get(language, "en")
        if st.button(translate_text("Play advice audio")):
            try:
                mp3_path = text_to_speech(translate_text(advice_text), gtts_lang)
                # stream audio
                with open(mp3_path, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3")
            except Exception as e:
                st.error(f"TTS error: {e}")

    # ----------------- Voice: Speech-to-Text via upload -----------------
    st.subheader(translate_text("🎤 Ask by voice (upload recorded audio)"))
    st.write(translate_text("Record a short voice note on your phone and upload it here (wav/mp3/m4a)."))
    uploaded_audio = st.file_uploader(translate_text("Upload voice file (optional)"), type=["wav", "mp3", "m4a", "ogg"])

    transcribed_text = None
    if uploaded_audio is not None:
        st.info(translate_text("Processing uploaded audio..."))
        transcription, trans_err = transcribe_audio(uploaded_audio)
        if trans_err:
            st.error(translate_text(trans_err))
        else:
            st.success(translate_text("Transcription:"))
            st.write(transcription)
            transcribed_text = transcription

    # ----------------- Mini chat (text fallback + handle transcribed input) -----------------
    st.write("---")
    st.subheader(translate_text("💬 Farmer Chat"))
    user_q = st.text_input(translate_text("Ask the Farmer Bot (or upload voice above)"))
    # prioritize uploaded transcription if present and user didn't type
    if not user_q and transcribed_text:
        user_q = transcribed_text

    if user_q:
        q = user_q.lower()
        if "irrigate" in q or "water" in q or "પાણી" in q or "सिंचाई" in q:
            reply = "If rain is expected soon, delay irrigation. Otherwise irrigate early morning or late evening."
        elif "fertilizer" in q or "યાવન" in q or "खाद" in q:
            reply = "Apply fertilizers on dry days and avoid doing so before heavy rain."
        elif "disease" in q or "રોગ" in q or "रोग" in q:
            reply = "High humidity raises disease risk — monitor crops and apply protective measures if necessary."
        elif "harvest" in q or "કાપણી" in q or "कटाई" in q:
            reply = "Harvest on dry days; avoid harvesting during or immediately after heavy rain."
        else:
            reply = "Weather looks moderate. Follow the provided advisory and re-check the forecast tomorrow."

        st.success(translate_text(reply))

    # ----------------- Radar & Map -----------------
    st.subheader(translate_text("📡 Radar / Layers"))
    st.write(translate_text("Tip: use the layer control to toggle overlays."))

    if _have_folium:
        try:
            rv_info = requests.get("https://api.rainviewer.com/public/maps.json", timeout=8).json()
            timestamps = rv_info.get("radar", {}).get("past", [])
            rv_times = [int(t) for t in timestamps] if timestamps else []
        except Exception:
            rv_times = []

        layer_choice = st.selectbox(
            translate_text("Select map layer"),
            ["None", "RainViewer Radar", "OWM Precipitation", "OWM Clouds"]
        )

        selected_time = None
        if layer_choice == "RainViewer Radar" and rv_times:
            idx = st.slider(translate_text("Radar frame (past)"),
                            min_value=0, max_value=len(rv_times)-1, value=len(rv_times)-1)
            selected_time = rv_times[idx]

        try:
            m = folium.Map(location=[lat, lon], zoom_start=8, control_scale=True)
            folium.TileLayer("cartodbpositron", name="Base Map").add_to(m)
            owm_key = api_key
            if layer_choice == "OWM Precipitation":
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.openweathermap.org/map/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={owm_key}",
                    attr="Precipitation © OpenWeatherMap", name="OWM Precipitation", opacity=0.6
                ).add_to(m)
            if layer_choice == "OWM Clouds":
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.openweathermap.org/map/clouds_new/{{z}}/{{x}}/{{y}}.png?appid={owm_key}",
                    attr="Clouds © OpenWeatherMap", name="OWM Clouds", opacity=0.6
                ).add_to(m)
            if layer_choice == "RainViewer Radar" and selected_time:
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.rainviewer.com/v2/radar/{selected_time}/{{z}}/{{x}}/{{y}}.png",
                    attr="Radar © RainViewer",
                    name=f"Radar ({datetime.utcfromtimestamp(selected_time).strftime('%Y-%m-%d %H:%M UTC')})",
                    opacity=0.6
                ).add_to(m)
            folium.CircleMarker([lat, lon], radius=6, color="blue", fill=True, popup=city).add_to(m)
            folium.LayerControl().add_to(m)
            st_folium(m, width=800, height=450)
        except Exception as e:
            st.warning(translate_text("Map could not be rendered. Showing basic map instead."))
            st.write(f":information_source: Map error: {e}")
            st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))
    else:
        st.info(translate_text("Map feature disabled. Please install 'folium' and 'streamlit-folium'."))
        if _folium_import_error:
            st.write(f":information_source: Folium import error: {_folium_import_error}")
        st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))

    st.markdown("---")
    st.write(translate_text("Tips:"))
    st.write("- " + translate_text("Record a short voice note (10-30s) and upload for quick questions."))
    st.write("- " + translate_text("Use Play Advice to hear the guidance in your selected language."))

# Helper functions used above (kept for completeness)
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
        lat = data[0]["lat"]
        lon = data[0]["lon"]
        return lat, lon, None
    except requests.exceptions.RequestException as e:
        return None, None, f"Network/geocode error: {e}"

def fetch_forecast_by_latlon(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, f"Forecast API error {r.status_code}: {r.text}"
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Network/forecast error: {e}"

def build_forecast_df(forecast_json):
    items = forecast_json.get("list", [])
    rows = []
    for it in items:
        dt = datetime.fromtimestamp(it.get("dt", 0))
        temp = it.get("main", {}).get("temp")
        hum = it.get("main", {}).get("humidity")
        rain = it.get("rain", {}).get("3h", 0.0) if it.get("rain") else 0.0
        cond = it.get("weather", [{}])[0].get("description", "").capitalize()
        wind = round(it.get("wind", {}).get("speed", 0.0) * 3.6, 1)
        rows.append({"Datetime": dt, "Date": dt.date(), "Temperature (°C)": temp,
                     "Humidity (%)": hum, "Rain (mm)": rain, "Condition": cond, "Wind (km/h)": wind})
    df = pd.DataFrame(rows)
    return df

def compose_advice(today_rain, avg_temp, avg_hum):
    if today_rain > 30:
        advice = "Heavy rain expected — avoid fertilizer application, secure harvested crops and livestock, and ensure drainage is clear."
    elif today_rain > 10:
        advice = "Moderate rain expected — delay irrigation and spraying; prepare drainage."
    elif today_rain > 0:
        advice = "Light rain expected — minimal irrigation needed; cover sensitive crops if forecast shows heavier rain later."
    else:
        advice = "No rain expected — schedule irrigation and fertilizer application on dry day."
    if avg_temp is not None:
        if avg_temp > 35:
            advice += " High temperatures — apply mulch and irrigate during cooler hours."
        elif avg_temp < 20:
            advice += " Cooler weather — suitable for sowing wheat and mustard."
    if avg_hum is not None and avg_hum > 85:
        advice += " High humidity — monitor for fungal diseases and consider protective treatments."
    return advice

def text_to_speech(text, lang_code):
    if not _have_gtts:
        raise RuntimeError(f"gTTS not available: {_gtts_error}")
    tts = gTTS(text=text, lang=lang_code)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    tts.save(tmp_name)
    return tmp_name

def transcribe_audio(uploaded_file):
    if not _have_speech_recognition:
        return None, f"SpeechRecognition not available: {_sr_error}"
    if not _have_pydub:
        return None, f"Pydub not available: {_pydub_error}"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as f:
            f.write(uploaded_file.read())
            src_path = f.name
    except Exception as e:
        return None, f"Failed to save upload: {e}"
    try:
        audio = AudioSegment.from_file(src_path)
        wav_path = src_path + ".wav"
        audio.export(wav_path, format="wav")
    except Exception as e:
        return None, f"Audio conversion failed (ffmpeg required): {e}"
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        sr_lang = "en-US"
        if language == "Hindi":
            sr_lang = "hi-IN"
        elif language == "Gujarati":
            sr_lang = "gu-IN"
        text = recognizer.recognize_google(audio_data, language=sr_lang)
        return text, None
    except Exception as e:
        return None, f"Transcription error: {e}"
    finally:
        try:
            os.remove(src_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass
