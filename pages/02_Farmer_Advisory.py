import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Farmer Advisory", layout="wide", page_icon="🌱")
st.title("🤖 Farmer Advisory Assistant")

# Sidebar
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])
crop = st.sidebar.selectbox("Select Crop", ["None", "Wheat", "Rice", "Maize"])
city = st.text_input("Enter city name:", "Ahmedabad")

# ---------------------- GEOCODING ----------------------
def geocode_city(city_name):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "results" not in data or len(data["results"]) == 0:
            return None, None, "City not found"
        return data["results"][0]["latitude"], data["results"][0]["longitude"], None
    except Exception as e:
        return None, None, f"Geocoding error: {e}"

# ---------------------- FORECAST ----------------------
def fetch_forecast(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,relative_humidity_2m,precipitation"
        "&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        "&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=12)
        return r.json(), None
    except Exception as e:
        return None, f"Forecast fetch error: {e}"

# ---------------------- BUILD DATAFRAME ----------------------
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
        })
    return pd.DataFrame(rows)

# ---------------------- ADVISORY ----------------------
def compose_advice(today_rain, avg_temp, avg_hum, crop=None):
    advice = ""
    if today_rain > 30:
        advice += "Heavy rain expected — avoid fertilizer and protect harvested crops. "
    elif today_rain > 10:
        advice += "Moderate rain — delay irrigation and spraying. "
    elif today_rain > 0:
        advice += "Light rain — minimal irrigation needed. "
    else:
        advice += "No rain — irrigation recommended today. "

    if avg_temp > 35:
        advice += "High temp — irrigate during cool hours. "
    elif avg_temp < 18:
        advice += "Cool temp — good for sowing wheat/mustard. "

    if avg_hum > 85:
        advice += "High humidity — fungal risk; monitor crops. "

    if crop == "Wheat":
        advice += " Wheat: Avoid waterlogging; maintain field drainage."
    elif crop == "Rice":
        advice += " Rice: Standing water is okay if rain is light."
    elif crop == "Maize":
        advice += " Maize: Protect against stem borers in humid weather."

    return advice

# ---------------------- MAIN APP ----------------------
if city:
    lat, lon, err = geocode_city(city)
    if err:
        st.error(err)
        st.stop()

    forecast_json, err = fetch_forecast(lat, lon)
    if err:
        st.error(err)
        st.stop()

    df = build_forecast_df(forecast_json)
    if df.empty:
        st.error("No forecast data")
        st.stop()

    # Daily aggregation
    df_daily = df.groupby("Date").agg({
        "Rain (mm)": "sum",
        "Temperature (°C)": "mean",
        "Humidity (%)": "mean"
    }).reset_index()

    today_rain = float(df_daily.iloc[0]["Rain (mm)"])
    avg_temp = float(df_daily["Temperature (°C)"].mean())
    avg_hum = float(df_daily["Humidity (%)"].mean())

    advice = compose_advice(today_rain, avg_temp, avg_hum, crop if crop != "None" else None)
    st.subheader("📋 Advice Summary")
    st.info(advice)
