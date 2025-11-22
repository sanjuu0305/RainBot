import streamlit as st
from utils import compose_advice, build_forecast_df, fetch_forecast, geocode_city

st.set_page_config(page_title="Farmer Advisory", layout="wide", page_icon="🌱")
st.title("🤖 Farmer Advisory Assistant")

# Sidebar
language = st.sidebar.selectbox("Language", ["English","Hindi","Gujarati"])
crop = st.sidebar.selectbox("Select Crop", ["None","Wheat","Rice","Maize"])
city = st.text_input("Enter city name:", "Ahmedabad")
api_key = st.secrets.get("openweather_api_key","")
if not api_key: st.error("API key missing"); st.stop()

if city:
    lat, lon, err = geocode_city(city, api_key)
    if err: st.error(err); st.stop()
    forecast_json, err = fetch_forecast(lat, lon, api_key)
    if err: st.error(err); st.stop()
    df = build_forecast_df(forecast_json)
    if df.empty: st.error("No forecast data"); st.stop()

    df_daily = df.groupby("Date").agg({"Rain (mm)":"sum","Temperature (°C)":"mean","Humidity (%)":"mean"}).reset_index()
    today_rain = float(df_daily.iloc[0]["Rain (mm)"])
    avg_temp = float(df_daily["Temperature (°C)"].mean())
    avg_hum = float(df_daily["Humidity (%)"].mean())
    
    advice = compose_advice(today_rain, avg_temp, avg_hum, crop if crop!="None" else None)
    st.subheader("📋 Advice Summary")
    st.info(advice)
