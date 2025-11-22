import streamlit as st
from utils import *
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="🌦️ Rain Forecast", layout="wide", page_icon="☔")
st.title("🌦️ Rain Forecast Dashboard")

# Sidebar
st.sidebar.header("Settings")
language = st.sidebar.selectbox("Language", ["English","Hindi","Gujarati"])
crop = st.sidebar.selectbox("Crop (optional)", ["None","Wheat","Rice","Maize"])

# API Key
api_key = st.secrets.get("openweather_api_key","")
if not api_key: st.error("Add OpenWeather API key"); st.stop()

# City input
city = st.text_input("Enter city name:", "Ahmedabad")
if city:
    lat, lon, err = geocode_city(city, api_key)
    if err: st.error(err); st.stop()

    forecast_json, err = fetch_forecast(lat, lon, api_key)
    if err: st.error(err); st.stop()

    df = build_forecast_df(forecast_json)
    if df.empty: st.error("No forecast data."); st.stop()

    # Hourly Chart
    st.subheader("Hourly Rain & Temperature")
    fig=go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"],y=df["Rain (mm)"],name="Rain",marker_color="skyblue"))
    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["Temperature (°C)"],mode="lines+markers",
                             name="Temp (°C)",yaxis="y2"))
    fig.update_layout(yaxis=dict(title="Rain (mm)"), yaxis2=dict(title="Temp (°C)",overlaying="y",side="right"))
    st.plotly_chart(fig,use_container_width=True)

    # Daily summary & advice
    st.subheader("Daily Rain Summary")
    df_daily = df.groupby("Date").agg({"Rain (mm)":"sum","Temperature (°C)":"mean","Humidity (%)":"mean"}).reset_index()
    st.dataframe(df_daily,use_container_width=True)

    today_rain = float(df_daily.iloc[0]["Rain (mm)"])
    avg_temp = float(df_daily["Temperature (°C)"].mean())
    avg_hum = float(df_daily["Humidity (%)"].mean())
    advice = compose_advice(today_rain, avg_temp, avg_hum, crop if crop!="None" else None)
    st.info(advice)

    # TTS
    st.subheader("🔊 Play Advice Audio")
    if st.button("Play advice"):
        try:
            mp3_path = text_to_speech(advice, {"English":"en","Hindi":"hi","Gujarati":"gu"}.get(language,"en"))
            with open(mp3_path,"rb") as f: audio_bytes=f.read()
            st.audio(audio_bytes, format="audio/mp3")
        except Exception as e: st.error(f"TTS error: {e}")
