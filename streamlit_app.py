import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from datetime import datetime
from deep_translator import GoogleTranslator
import json

# ----------------- Streamlit Setup -----------------
st.set_page_config(page_title="🌦️ Rain Forecast", layout="wide", initial_sidebar_state="expanded")

# ----------------- Sidebar: Language Selector -----------------
language = st.sidebar.selectbox("🌐 Choose Language", ["English", "Hindi", "Gujarati"])

def translate_text(text, target_lang):
    if target_lang == "English":
        return text
    elif target_lang == "Hindi":
        return GoogleTranslator(source='auto', target='hi').translate(text)
    elif target_lang == "Gujarati":
        return GoogleTranslator(source='auto', target='gu').translate(text)

# ----------------- API Config -----------------
api_key = st.secrets.get("openweather_api_key", "YOUR_OPENWEATHERMAP_API_KEY")

# ----------------- Input: Location -----------------
st.title(translate_text("🌦️ Rain Forecast Dashboard", language))
city = st.text_input(translate_text("Enter your city name:", language), "Ahmedabad")

# ----------------- Geolocation -----------------
if city:
    geolocator = Nominatim(user_agent="geoapiExercises")
    location = geolocator.geocode(city)
    if location:
        lat, lon = location.latitude, location.longitude

        # ----------------- Fetch Weather Data -----------------
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        response = requests.get(url)
        data = response.json()

        if response.status_code == 200:
            forecast_list = data['list']

            # Extract Rain Data
            times, rain_amounts, humidity = [], [], []
            for item in forecast_list:
                times.append(datetime.fromtimestamp(item['dt']))
                rain = item.get('rain', {}).get('3h', 0)
                rain_amounts.append(rain)
                humidity.append(item['main']['humidity'])

            df = pd.DataFrame({
                'Time': times,
                'Rainfall (mm)': rain_amounts,
                'Humidity (%)': humidity
            })

            # ----------------- Hourly Rainfall Chart -----------------
            st.subheader(translate_text("🕒 Hourly Rainfall Forecast", language))
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['Time'], y=df['Rainfall (mm)'], name='Rainfall (mm)'))
            fig.add_trace(go.Scatter(x=df['Time'], y=df['Humidity (%)'], name='Humidity (%)', yaxis='y2'))

            fig.update_layout(
                xaxis_title="Time",
                yaxis_title="Rainfall (mm)",
                yaxis2=dict(title="Humidity (%)", overlaying="y", side="right"),
                template="plotly_dark",
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

            # ----------------- 7-Day Average Summary -----------------
            st.subheader(translate_text("📊 7-Day Average Rainfall Summary", language))
            daily_avg = df.groupby(df['Time'].dt.date).mean(numeric_only=True)
            st.dataframe(daily_avg)

            # ----------------- Flood Risk Index -----------------
            avg_rain = df['Rainfall (mm)'].mean()
            avg_humidity = df['Humidity (%)'].mean()
            risk_score = (avg_rain * 0.7) + (avg_humidity * 0.3)
            if risk_score < 20:
                risk_level = translate_text("Low", language)
                color = "green"
            elif risk_score < 50:
                risk_level = translate_text("Moderate", language)
                color = "orange"
            else:
                risk_level = translate_text("High", language)
                color = "red"

            st.subheader(translate_text("💧 Real-Time Flood Risk Index", language))
            st.markdown(f"<h3 style='color:{color}'>{translate_text('Flood Risk Level:', language)} {risk_level}</h3>", unsafe_allow_html=True)

            # ----------------- Map View -----------------
            st.subheader(translate_text("📍 Map View - Rainfall Area", language))
            st.map(pd.DataFrame([[lat, lon]], columns=['lat', 'lon']))

            # ----------------- Rain Alerts (Optional) -----------------
            st.subheader(translate_text("📲 Rain Alert (Optional)", language))
            st.info(translate_text("You can connect your Telegram bot or email to get alerts.", language))
            st.write(translate_text("Configure via st.secrets or UI fields below.", language))

            telegram_token = st.text_input("🔑 Telegram Token (Optional)", type="password")
            telegram_chat_id = st.text_input("💬 Chat ID (Optional)")

            if st.button(translate_text("Send Test Alert", language)):
                if telegram_token and telegram_chat_id:
                    message = f"🌧️ Rain Alert for {city}! Flood Risk: {risk_level}"
                    send_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                    requests.post(send_url, data={"chat_id": telegram_chat_id, "text": message})
                    st.success(translate_text("Alert sent successfully!", language))
                else:
                    st.warning(translate_text("Please enter both Telegram token and chat ID.", language))

        else:
            st.error(translate_text("Failed to fetch weather data. Please check your API key.", language))
    else:
        st.error(translate_text("City not found. Please enter a valid location.", language))