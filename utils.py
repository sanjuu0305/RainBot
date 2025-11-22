import requests
import pandas as pd
from datetime import datetime
from gtts import gTTS
import tempfile
import os

# ------------------- Geocoding -------------------
def geocode_city(city, api_key):
    """Get latitude and longitude for a city using OpenWeatherMap Geocoding API."""
    try:
        r = requests.get(
            "http://api.openweathermap.org/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": api_key},
            timeout=10
        )
        if r.status_code != 200:
            return None, None, f"API error {r.status_code}: {r.text}"
        data = r.json()
        if not data:
            return None, None, "No results found for city."
        return data[0]["lat"], data[0]["lon"], None
    except Exception as e:
        return None, None, f"Geocoding error: {e}"

# ------------------- Forecast -------------------
def fetch_forecast(lat, lon, api_key):
    """Fetch 5-day forecast from OpenWeatherMap API."""
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
            timeout=10
        )
        if r.status_code != 200:
            return None, f"API error {r.status_code}: {r.text}"
        return r.json(), None
    except Exception as e:
        return None, f"Forecast fetch error: {e}"

# ------------------- Build DataFrame -------------------
def build_forecast_df(forecast_json):
    """Convert forecast JSON into a Pandas DataFrame with useful columns."""
    items = forecast_json.get("list", [])
    rows = []
    for it in items:
        dt = datetime.fromtimestamp(it.get("dt", 0))
        temp = it.get("main", {}).get("temp")
        hum = it.get("main", {}).get("humidity")
        rain = it.get("rain", {}).get("3h", 0.0) if it.get("rain") else 0.0
        cond = it.get("weather", [{}])[0].get("description", "").capitalize()
        wind = round(it.get("wind", {}).get("speed", 0.0) * 3.6, 1)  # km/h
        rows.append({
            "Datetime": dt,
            "Date": dt.date(),
            "Temperature (°C)": temp,
            "Humidity (%)": hum,
            "Rain (mm)": rain,
            "Condition": cond,
            "Wind (km/h)": wind
        })
    return pd.DataFrame(rows)

# ------------------- Farmer Advice -------------------
def compose_advice(today_rain, avg_temp, avg_hum, crop=None):
    """Generate farming advice based on rain, temperature, humidity, and crop."""
    advice = ""
    # Rain-based advice
    if today_rain > 30:
        advice = "Heavy rain — avoid fertilizer, secure crops and livestock."
    elif today_rain > 10:
        advice = "Moderate rain — delay irrigation, prepare drainage."
    elif today_rain > 0:
        advice = "Light rain — minimal irrigation needed."
    else:
        advice = "No rain — schedule irrigation and fertilizer application."

    # Temperature advice
    if avg_temp:
        if avg_temp > 35:
            advice += " High temperature — irrigate in cooler hours."
        elif avg_temp < 20:
            advice += " Cooler weather — good for sowing wheat/mustard."

    # Humidity advice
    if avg_hum and avg_hum > 85:
        advice += " High humidity — monitor fungal diseases."

    # Crop-specific advice
    if crop:
        advice += f" Crop-specific advice for {crop}."

    return advice

# ------------------- Text-to-Speech -------------------
def text_to_speech(text, lang_code="en"):
    """
    Convert text to speech and return path to temporary MP3 file.
    Caller should handle deletion if needed.
    """
    try:
        tts = gTTS(text=text, lang=lang_code)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_name = tmp.name
        tmp.close()
        tts.save(tmp_name)
        return tmp_name
    except Exception as e:
        raise RuntimeError(f"TTS generation failed: {e}")
