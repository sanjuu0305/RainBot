import streamlit as st
import plotly.graph_objects as go
from utils import geocode_city, fetch_forecast, build_forecast_df, translate_text

st.set_page_config(page_title="Rain Forecast", layout="wide", page_icon="🌦️")
st.title("🌦️ Rain Forecast")

# Sidebar
language = st.sidebar.selectbox("Language", ["English","Hindi","Gujarati"])
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

    # Hourly Chart
    st.subheader("🕒 Hourly Rain & Temperature (3-hour steps)")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name="Rain (mm)", marker_color="skyblue"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"], mode="lines+markers",
                             name="Temperature (°C)", yaxis="y2"))
    fig.update_layout(yaxis=dict(title="Rain (mm)"), yaxis2=dict(title="Temp (°C)", overlaying="y", side="right"))
    st.plotly_chart(fig, use_container_width=True)

    # Daily Summary
    st.subheader("📊 Daily Rain Summary")
    df_daily = df.groupby("Date").agg({"Rain (mm)":"sum","Temperature (°C)":"mean","Humidity (%)":"mean"}).reset_index()
    st.dataframe(df_daily, use_container_width=True)
