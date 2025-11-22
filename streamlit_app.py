import streamlit as st
from utils import *

st.set_page_config(page_title="🌦️ Rain Forecast Pro", layout="wide", page_icon="☔")
st.title("🌦️ Rain Forecast Dashboard")

# --- Sidebar ---
st.sidebar.header("🌐 Choose language")
language=st.sidebar.selectbox("Language", ["English","Hindi","Gujarati"])
crop=st.sidebar.selectbox("Select crop (optional)", ["None","Wheat","Rice","Maize"])

# --- API Key ---
api_key=st.secrets.get("openweather_api_key","")
if not api_key:
    st.error("API key missing. Add 'openweather_api_key' in Streamlit Secrets.")
    st.stop()

# --- City input ---
city=st.text_input("Enter city name:","Ahmedabad")
if city:
    with st.spinner("Finding location..."):
        lat,lon,err=geocode_city(city,api_key)
    if err: st.error(f"City error: {err}"); st.stop()

    with st.spinner("Fetching forecast..."):
        forecast_json,err=fetch_forecast(lat,lon,api_key)
    if err: st.error(f"Forecast error: {err}"); st.stop()

    df=build_forecast_df(forecast_json)
    if df.empty: st.error("No forecast data."); st.stop()

    # --- Charts ---
    import plotly.graph_objects as go
    st.subheader("🕒 Hourly Rain & Temperature")
    fig=go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"],y=df["Rain (mm)"],name="Rain (mm)",marker_color="skyblue"))
    fig.add_trace(go.Scatter(x=df["Datetime"],y=df["Temperature (°C)"],mode="lines+markers",
                             name="Temp (°C)",yaxis="y2"))
    fig.update_layout(yaxis=dict(title="Rain (mm)"),
                      yaxis2=dict(title="Temp (°C)",overlaying="y",side="right"))
    st.plotly_chart(fig,use_container_width=True)

    # --- Daily summary & advice ---
    st.subheader("📊 Daily Rain Summary")
    df_daily=df.groupby("Date").agg({"Rain (mm)":"sum","Temperature (°C)":"mean","Humidity (%)":"mean"}).reset_index()
    st.dataframe(df_daily,use_container_width=True)

    today_rain=float(df_daily.iloc[0]["Rain (mm)"])
    avg_temp=float(df_daily["Temperature (°C)"].mean())
    avg_hum=float(df_daily["Humidity (%)"].mean())
    advice=compose_advice(today_rain,avg_temp,avg_hum,crop if crop!="None" else None)
    st.info(advice)

    # --- TTS ---
    st.subheader("🔊 Play Advice (Voice)")
    if st.button("Play advice audio"):
        try:
            mp3=text_to_speech(advice,lang_code={"English":"en","Hindi":"hi","Gujarati":"gu"}.get(language,"en"))
            with open(mp3,"rb") as f: audio_bytes=f.read()
            st.audio(audio_bytes,format="audio/mp3")
        except Exception as e: st.error(f"TTS error: {e}")

    # --- STT ---
    st.subheader("🎤 Ask by voice (upload)")
    uploaded=st.file_uploader("Upload audio (wav/mp3/m4a)",type=["wav","mp3","m4a"])
    if uploaded:
        text,err=transcribe_audio(uploaded,language)
        if err: st.error(err)
        else: st.success(f"Transcribed: {text}")

