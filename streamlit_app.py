import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from streamlit_lottie import st_lottie

# ----------------- Page Setup -----------------
st.set_page_config(page_title="🌦️ Rain Forecast App", layout="wide", page_icon="🌧️")

st.title("🌧️ Rain Forecast Prediction")
st.markdown("Get **5-Day Rain & Weather Forecast** for your city 🌍")

# Optional Lottie animation
def load_lottie(url):
    try:
        return requests.get(url).json()
    except:
        return None

lottie_weather = load_lottie("https://assets10.lottiefiles.com/packages/lf20_obhph3sh.json")
st_lottie(lottie_weather, height=150, key="weather_anim")

# ----------------- Input Section -----------------
col1, col2 = st.columns([2, 1])
with col1:
    city = st.text_input("🏙️ Enter City Name:", "Ahmedabad")
with col2:
    units = st.selectbox("🌡️ Units", ["metric (°C)", "imperial (°F)"])

unit_system = "metric" if "metric" in units else "imperial"

# ----------------- API Key -----------------
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error("❌ API key not found. Add your OpenWeatherMap API key in Streamlit Secrets (Settings → Secrets).")
    st.info('Example secrets.toml entry:\n\napi_key = "your_real_api_key_here"')
    st.stop()

# ----------------- Fetch Forecast -----------------
if st.button("🔍 Get Rain Forecast"):
    with st.spinner("Fetching latest weather data..."):
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units={unit_system}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"⚠️ Network or API error: {e}")
            st.stop()

        if data.get("cod") != "200":
            st.error(f"❌ Error: {data.get('message', 'Invalid city name or API issue.')}")
            st.stop()

        forecast_list = data.get("list", [])
        if not forecast_list:
            st.warning("No forecast data available.")
            st.stop()

        # ----------------- Create DataFrame -----------------
        df = pd.DataFrame([{
            "Datetime": datetime.fromtimestamp(item["dt"]),
            "Temperature": item["main"]["temp"],
            "Humidity": item["main"]["humidity"],
            "Rain (mm)": item.get("rain", {}).get("3h", 0.0),
            "Weather": item["weather"][0]["description"].capitalize()
        } for item in forecast_list])

        # ----------------- Current Weather -----------------
        current = forecast_list[0]
        st.subheader(f"📍 Current Weather in {city.capitalize()}")
        c1, c2, c3 = st.columns(3)
        c1.metric("🌡 Temperature", f"{current['main']['temp']:.1f}°")
        c2.metric("💧 Humidity", f"{current['main']['humidity']}%")
        c3.metric("☁️ Condition", current['weather'][0]['description'].capitalize())

        # ----------------- Daily Rain Summary -----------------
        st.subheader("📅 5-Day Rainfall Summary")
        df_daily = df.groupby(df["Datetime"].dt.date)["Rain (mm)"].sum().reset_index()
        df_daily.columns = ["Date", "Rain (mm)"]

        st.dataframe(df_daily, use_container_width=True)

        # ----------------- Rainfall Chart -----------------
        fig_rain = go.Figure()
        fig_rain.add_trace(go.Bar(
            x=df_daily["Date"],
            y=df_daily["Rain (mm)"],
            name="Rainfall (mm)",
            marker_color="skyblue"
        ))
        fig_rain.update_layout(
            title="🌧️ Rainfall Forecast (Next 5 Days)",
            xaxis_title="Date",
            yaxis_title="Rain (mm)"
        )
        st.plotly_chart(fig_rain, use_container_width=True)

        # ----------------- Temperature & Humidity Trend -----------------
        st.subheader("🌡️ Temperature and Humidity Trend (Next 5 Days)")
        fig_weather = go.Figure()
        fig_weather.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature"], name="Temperature", mode="lines+markers"))
        fig_weather.add_trace(go.Scatter(x=df["Datetime"], y=df["Humidity"], name="Humidity (%)", mode="lines+markers", yaxis="y2"))

        fig_weather.update_layout(
            title="Temperature & Humidity Trend",
            xaxis_title="Datetime",
            yaxis=dict(title="Temperature", side="left"),
            yaxis2=dict(title="Humidity (%)", overlaying="y", side="right")
        )
        st.plotly_chart(fig_weather, use_container_width=True)

        # ----------------- Success Message -----------------
        st.success("✅ Rain forecast successfully fetched!")

        # ----------------- Optional: Map Display -----------------
        coord = data.get("city", {}).get("coord", {})
        if coord:
            st.map(pd.DataFrame({"lat": [coord["lat"]], "lon": [coord["lon"]]}))

        st.caption("Data Source: OpenWeatherMap.org")