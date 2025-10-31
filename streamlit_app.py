import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium

# ----------------- App Setup -----------------
st.set_page_config(page_title="🌦️ Rain Forecast Pro", layout="wide", page_icon="☔")

st.title("☔ Rain Forecast Pro – Weather, Alerts & Flood Risk")
st.markdown("An AI-powered rain monitoring dashboard 🌧️ for local users (India Edition 🇮🇳)")

# ----------------- User Inputs -----------------
city = st.text_input("🏙️ Enter City Name:", "Ahmedabad")
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error("⚠️ API key missing! Add your OpenWeatherMap API key in Streamlit → Settings → Secrets.")
    st.stop()

# ----------------- Fetch Data -----------------
def get_weather_data(city):
    url_forecast = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
    res = requests.get(url_forecast)
    if res.status_code != 200:
        return None
    data = res.json()
    lat = data["city"]["coord"]["lat"]
    lon = data["city"]["coord"]["lon"]

    forecast_list = data["list"]
    df = pd.DataFrame([{
        "Datetime": datetime.fromtimestamp(item["dt"]),
        "Temperature (°C)": item["main"]["temp"],
        "Humidity (%)": item["main"]["humidity"],
        "Rain (mm)": item.get("rain", {}).get("3h", 0.0),
        "Weather": item["weather"][0]["description"].capitalize(),
        "Wind (km/h)": round(item["wind"]["speed"] * 3.6, 1)
    } for item in forecast_list])

    df["Date"] = df["Datetime"].dt.date
    return df, lat, lon

data, lat, lon = get_weather_data(city)

if data is None:
    st.error("❌ City not found or API issue.")
    st.stop()

# ----------------- Map View -----------------
st.subheader("📍 Rain Intensity Map")
m = folium.Map(location=[lat, lon], zoom_start=7)
folium.TileLayer("cartodbpositron").add_to(m)
folium.Marker([lat, lon], popup=f"{city}", tooltip=f"{city}").add_to(m)
folium.raster_layers.TileLayer(
    tiles="https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=" + api_key,
    attr="Rain Data © OpenWeatherMap",
    name="Rainfall",
    opacity=0.5
).add_to(m)
folium.LayerControl().add_to(m)
st_folium(m, width=700, height=500)

# ----------------- Hourly Forecast -----------------
st.subheader("🕒 Hourly Forecast (Next 48 Hours)")
fig_hourly = go.Figure()
fig_hourly.add_trace(go.Bar(x=data["Datetime"], y=data["Rain (mm)"], name="Rain (mm)"))
fig_hourly.add_trace(go.Scatter(x=data["Datetime"], y=data["Temperature (°C)"], name="Temperature (°C)", mode="lines+markers"))
fig_hourly.update_layout(title="Hourly Rain & Temperature", xaxis_title="Time", yaxis_title="Rain (mm) / Temperature (°C)")
st.plotly_chart(fig_hourly, use_container_width=True)

# ----------------- 7-Day Average Summary -----------------
st.subheader("📊 7-Day Average Rainfall Summary")
df_daily = data.groupby("Date").agg({
    "Rain (mm)": "sum",
    "Temperature (°C)": "mean",
    "Humidity (%)": "mean"
}).reset_index()
fig_summary = go.Figure()
fig_summary.add_trace(go.Bar(x=df_daily["Date"], y=df_daily["Rain (mm)"], name="Rain (mm)"))
fig_summary.update_layout(title="Daily Rainfall Trend", xaxis_title="Date", yaxis_title="Rain (mm)")
st.plotly_chart(fig_summary, use_container_width=True)

# ----------------- Flood Risk Index -----------------
st.subheader("💧 Real-Time Flood Risk Index")
avg_rain = df_daily["Rain (mm)"].mean()
avg_humidity = df_daily["Humidity (%)"].mean()

if avg_rain > 20 and avg_humidity > 80:
    flood_risk = "🚨 HIGH – Flood risk possible! (ભારે વરસાદની શક્યતા)"
elif avg_rain > 10 and avg_humidity > 70:
    flood_risk = "⚠️ MEDIUM – Watch weather updates. (મધ્યમ વરસાદ)"
else:
    flood_risk = "✅ LOW – No flood risk. (સુરક્ષિત સ્થિતિ)"

st.info(flood_risk)

# ----------------- Rain Alert via Telegram -----------------
st.subheader("📲 Rain Alert Notification")
st.markdown("You can get daily rain alerts on Telegram using your bot token and chat ID.")

telegram_token = st.text_input("Enter Telegram Bot Token (optional):", type="password")
chat_id = st.text_input("Enter Your Telegram Chat ID (optional):")

if st.button("Send Rain Alert"):
    if telegram_token and chat_id:
        rain_today = df_daily.iloc[0]["Rain (mm)"]
        alert_msg = f"🌧️ Rain Alert for {city}!\nToday's Rain: {rain_today:.2f} mm\nFlood Risk: {flood_risk}"
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        requests.post(telegram_url, data={"chat_id": chat_id, "text": alert_msg})
        st.success("✅ Alert sent successfully to your Telegram!")
    else:
        st.warning("Please enter both Telegram Bot Token and Chat ID to send alerts.")