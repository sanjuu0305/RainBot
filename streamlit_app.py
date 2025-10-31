import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ----------------- App Setup -----------------
st.set_page_config(page_title="Rain Forecast", layout="centered", page_icon="🌦️")

st.title("🌧️ Rain Forecast Prediction App")
st.markdown("Enter your city name to get 5-day rain and weather forecast.")

# ----------------- User Input -----------------
city = st.text_input("Enter City Name:", "Ahmedabad")

# Your OpenWeatherMap API key (get from https://openweathermap.org/api)
api_key = "245b3686bfd9ad40841d5a99c91d11db"

# ----------------- Fetch Data -----------------
if st.button("Get Rain Forecast"):
    if api_key == "245b3686bfd9ad40841d5a99c91d11db":
        st.error("Please replace 'YOUR_API_KEY' with your OpenWeatherMap API key.")
    else:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Extract data
            forecast_list = data["list"]
            df = pd.DataFrame([{
                "Datetime": datetime.fromtimestamp(item["dt"]),
                "Temperature (°C)": item["main"]["temp"],
                "Humidity (%)": item["main"]["humidity"],
                "Rain (mm)": item.get("rain", {}).get("3h", 0),
                "Weather": item["weather"][0]["description"].capitalize()
            } for item in forecast_list])

            # Display current weather
            current = forecast_list[0]
            st.subheader(f"📍 Current Weather in {city.capitalize()}")
            st.metric("Temperature (°C)", f"{current['main']['temp']:.1f}")
            st.metric("Humidity (%)", current['main']['humidity'])
            st.metric("Weather", current['weather'][0]['description'].capitalize())

            # Rain forecast
            st.subheader("🌧️ 5-Day Rain Forecast")
            df_daily = df.groupby(df["Datetime"].dt.date)["Rain (mm)"].sum().reset_index()

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
        else:
            st.error("City not found or API error. Please check your city name.")