import requests
import pandas as pd
from datetime import datetime, date
from gtts import gTTS
import tempfile
import os

# ----------------- Geocoding -----------------
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

# ----------------- Forecast -----------------
def fetch_forecast(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
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

# ----------------- Build Hourly DataFrame -----------------
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

# ----------------- Build Daily DataFrame -----------------
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

# ----------------- Farmer Advisory -----------------
def compose_advice(today_rain, avg_temp, avg_hum, crop=None):
    advice=""
    # Rain
    if today_rain > 30:
        advice="Heavy rain — avoid fertilizer, secure crops and drainage."
    elif today_rain > 10:
        advice="Moderate rain — delay irrigation, prepare drainage."
    elif today_rain > 0:
        advice="Light rain — minimal irrigation needed."
    else:
        advice="No rain — schedule irrigation/fertilizer on dry day."

    # Temperature alerts
    if avg_temp:
        if avg_temp > 40:
            advice += " ⚠️ Very hot day — protect crops and livestock."
        elif avg_temp < 10:
            advice += " ❄️ Very cold day — protect sensitive crops."
        elif avg_temp > 35:
            advice += " High temperature — irrigate during cooler hours."
        elif avg_temp < 20:
            advice += " Cooler weather — good for sowing wheat/mustard."

    # Humidity
    if avg_hum and avg_hum > 85:
        advice += " High humidity — monitor fungal diseases."

    # Crop-specific advice
    if crop:
        advice += f" Crop-specific advice for {crop}."

    return advice

# ----------------- Text-to-Speech -----------------
def text_to_speech(text, lang_code="en"):
    tts = gTTS(text=text, lang=lang_code)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    tts.save(tmp_name)
    return tmp_name

# ----------------- Speech-to-Text -----------------
def transcribe_audio(uploaded_file, language="English"):
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError:
        return None, "SpeechRecognition or pydub not installed"

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
        os.remove(src)
        os.remove(wav)
        return text, None
    except Exception as e:
        return None, f"Transcription error: {e}"
