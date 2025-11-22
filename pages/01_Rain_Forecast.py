import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from utils import *
import tempfile

st.set_page_config(page_title="🌦️ Rain Forecast", layout="wide", page_icon="☔")
st.title("🌦️ Rain Forecast Dashboard")

# Sidebar
st.sidebar.header("Settings")
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])
crop = st.sidebar.selectbox("Crop (optional)", ["None", "Wheat", "Rice", "Maize"])

# ---------------------- NO API KEY NEEDED ---------------------
st.success("Using Open-Meteo (No API Key Required)")

# ---------------------- INPUT CITY ----------------------------
city = st.text_input("Enter city name:", "Ahmedabad")

# ---------------------- GEOCODING (Open-Meteo) -----------------
def geocode_city(city):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "results" not in data or len(data["results"]) == 0:
            return None, None, "City not found"
        return data["results"][0]["latitude"], data["results"][0]["longitude"], None
    except Exception as e:
        return None, None, f"Geocoding error: {e}"

# ---------------------- FORECAST (Open-Meteo) ------------------
def fetch_forecast(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        "&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        "&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=12)
        return r.json(), None
    except Exception as e:
        return None, f"Forecast fetch error: {e}"

# ---------------------- BUILD FORECAST DF ----------------------
def build_forecast_df(data):
    hourly = data.get("hourly", {})
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
            "Wind (km/h)": hourly["wind_speed_10m"][i],
        })
    return pd.DataFrame(rows)

# ---------------------- ADVISORY -------------------------------
def compose_advice(rain, temp, hum, crop=None):
    advice = ""

    if rain > 30:
        advice += "Heavy rain expected — avoid fertilizer and protect harvested crops. "
    elif rain > 10:
        advice += "Moderate rain — delay irrigation and spraying. "
    elif rain > 0:
        advice += "Light rain — minimal irrigation needed. "
    else:
        advice += "No rain — irrigation recommended today. "

    if temp > 35:
        advice += "High temp — irrigate during cool hours. "
    elif temp < 18:
        advice += "Cool temp — good for sowing wheat/mustard. "

    if hum > 85:
        advice += "High humidity — fungal risk; monitor crops. "

    # Crop-specific advice
    if crop == "Wheat":
        advice += " Wheat: Avoid waterlogging; maintain field drainage."
    elif crop == "Rice":
        advice += " Rice: Standing water is okay if rain is light."
    elif crop == "Maize":
        advice += " Maize: Protect against stem borers in humid weather."

    return advice

# ---------------------- TTS ---------------------
from gtts import gTTS

def text_to_speech(text, lang):
    tts = gTTS(text=text, lang=lang)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(tmp.name)
    return tmp.name

# =================================================================
#                       MAIN APP LOGIC
# =================================================================
if city:
    lat, lon, err = geocode_city(city)
    if err: st.error(err); st.stop()

    data, err = fetch_forecast(lat, lon)
    if err: st.error(err); st.stop()

    df = build_forecast_df(data)
    if df.empty:
        st.error("No forecast data.")
        st.stop()

    # ---------------------- CHART ----------------------
    st.subheader("Hourly Rain & Temperature")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name="Rain (mm)", marker_color="skyblue"))
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df["Temperature (°C)"],
            name="Temperature (°C)",
            mode="lines+markers",
            yaxis="y2"
        )
    )

    fig.update_layout(
        yaxis=dict(title="Rain (mm)"),
        yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right")
    )

    st.plotly_chart(fig, use_container_width=True)

    # ---------------------- DAILY SUMMARY ----------------------
    st.subheader("Daily Rain Summary")
    df_daily = df.groupby("Date").agg({
        "Rain (mm)": "sum",
        "Temperature (°C)": "mean",
        "Humidity (%)": "mean"}).reset_index()
    st.dataframe(df_daily, use_container_width=True)

    # ---------------------- ADVISORY ----------------------
    today_rain = df_daily.iloc[0]["Rain (mm)"]
    avg_temp = df_daily["Temperature (°C)"].mean()
    avg_hum = df_daily["Humidity (%)"].mean()

    advice = compose_advice(today_rain, avg_temp, avg_hum, crop if crop != "None" else None)
    st.subheader("🌾 Farmer Advisory")
    st.info(advice)

    # ---------------------- TTS ----------------------
    st.subheader("🔊 Play Advice Audio")
    if st.button("Play advice"):
        lang_map = {"English": "en", "Hindi": "hi", "Gujarati": "gu"}
        path = text_to_speech(advice, lang_map.get(language, "en"))
        st.audio(open(path, "rb").read(), format="audio/mp3")
