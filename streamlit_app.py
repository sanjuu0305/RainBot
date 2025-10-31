import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ----------------- App Setup -----------------
st.set_page_config(page_title="Rain Forecast", layout="centered", page_icon="🌦️")

st.title("🌧️ Rain Forecast Prediction App")
st.markdown("Enter your city name to get 5-day rain and weather forecast.")


city = st.text_input("Enter City Name:", "Ahmedabad")

# Get API key from Streamlit secrets (use .get to avoid KeyError)
api_key = st.secrets.get("api_key", "")

# If no api_key, show helpful message and stop
if not api_key:
    st.error("API key not found. Add your OpenWeatherMap API key to Streamlit Secrets (Settings → Secrets).")
    st.info('Example secrets.toml entry:\n\napi_key = "your_real_api_key_here"')
    st.stop()

# ----------------- Fetch Data -----------------
if st.button("Get Rain Forecast"):
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as e:
        st.error(f"Network error: {e}")
        st.stop()

    if response.status_code == 200:
        data = response.json()

        # Extract data
        forecast_list = data.get("list", [])
        if not forecast_list:
            st.error("No forecast data received from API.")
            st.stop()

        df = pd.DataFrame([{
            "Datetime": datetime.fromtimestamp(item["dt"]),
            "Temperature (°C)": item["main"]["temp"],
            "Humidity (%)": item["main"]["humidity"],
            "Rain (mm)": item.get("rain", {}).get("3h", 0.0),
            "Weather": item["weather"][0]["description"].capitalize()
        } for item in forecast_list])

        # Display current weather (first forecast entry)
        current = forecast_list[0]
        st.subheader(f"📍 Current Weather in {city.capitalize()}")
        st.metric("Temperature (°C)", f"{current['main']['temp']:.1f}")
        st.metric("Humidity (%)", current['main']['humidity'])
        st.metric("Weather", current['weather'][0]['description'].capitalize())

        # Rain forecast (group by date)
        st.subheader("🌧️ 5-Day Rain Forecast")
        df_daily = df.groupby(df["Datetime"].dt.date)["Rain (mm)"].sum().reset_index()
        df_daily["Datetime"] = pd.to_datetime(df_daily["Datetime"]).dt.date  # nicer labels

        fig_rain = go.Figure()
        fig_rain.add_trace(go.Bar(
            x=df_daily["Datetime"],
            y=df_daily["Rain (mm)"],
            name="Rainfall (mm)"
        ))
        fig_rain.update_layout(title="Rainfall Forecast (Next 5 Days)", xaxis_title="Date", yaxis_title="Rain (mm)")
        st.plotly_chart(fig_rain, use_container_width=True)

        # Temperature & Humidity chart
        st.subheader("🌡️ Temperature and Humidity Trend")
        fig_weather = go.Figure()
        fig_weather.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"], name="Temperature (°C)", mode="lines+markers"))
        fig_weather.add_trace(go.Scatter(x=df["Datetime"], y=df["Humidity (%)"], name="Humidity (%)", mode="lines+markers", yaxis="y2"))

        fig_weather.update_layout(
            title="Temperature & Humidity (Next 5 Days)",
            xaxis_title="Datetime",
            yaxis=dict(title="Temperature (°C)", side="left"),
            yaxis2=dict(title="Humidity (%)", overlaying="y", side="right")
        )
        st.plotly_chart(fig_weather, use_container_width=True)

        st.success("✅ Rain forecast successfully fetched!")
    elif response.status_code == 401:
        st.error("Unauthorized: Check your API key (401).")
    elif response.status_code == 404:
        st.error("City not found (404). Please check the city name.")
    else:
        st.error(f"API error: {response.status_code} - {response.text}")