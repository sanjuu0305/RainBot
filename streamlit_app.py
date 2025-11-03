# streamlit_app.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import altair as alt

# ---------- CONFIG ----------
st.set_page_config(page_title="Live Rain Forecast for Farmers", layout="wide")

OPENWEATHER_API_KEY = "YOUR_API_KEY_HERE"  # 🔑 Replace this with your API key

# ---------- Translation Helper ----------
def translate_text(text, language):
    gu_map = {
        "City": "શહેર",
        "Rain Forecast": "વરસાદ અનુમાન",
        "Temperature": "તાપમાન",
        "Humidity": "આર્દ્રતા",
        "Flood Risk": "પૂર જોખમ",
        "Farmer Advisory": "કિસાન સલાહ",
        "Crop Suggestion": "ફસલ સૂચન",
        "Light rain": "હળવો વરસાદ",
        "Heavy rain": "ભારે વરસાદ",
        "No rain": "કોઈ વરસાદ નહીં"
    }
    if language == "ગુજરાતી":
        return gu_map.get(text, text)
    return text

# ---------- Sidebar Input ----------
st.sidebar.header("🌆 City & Local Areas")
language = st.sidebar.selectbox("Choose Language", ["English", "ગુજરાતી"])
city = st.sidebar.text_input("Enter main city name", "Surat")
areas = st.sidebar.text_input("Enter 3 nearby local areas (comma separated)", "Bardoli, Kamrej, Olpad")

# ---------- Helper Function ----------
def get_weather_forecast(city_name):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={OPENWEATHER_API_KEY}&units=metric"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    data = res.json()
    forecast = []
    for item in data["list"]:
        dt = datetime.fromtimestamp(item["dt"])
        rain = item.get("rain", {}).get("3h", 0)
        temp = item["main"]["temp"]
        humidity = item["main"]["humidity"]
        desc = item["weather"][0]["description"]
        forecast.append({
            "Date": dt,
            "Rain (mm)": rain,
            "Temperature (°C)": temp,
            "Humidity (%)": humidity,
            "Description": desc
        })
    return pd.DataFrame(forecast)

# ---------- Analysis Function ----------
def analyze_forecast(df):
    rain_total = df["Rain (mm)"].sum()
    avg_temp = df["Temperature (°C)"].mean()
    avg_humidity = df["Humidity (%)"].mean()

    if rain_total > 50:
        flood_risk = "🚨 HIGH — Flood risk likely"
    elif rain_total > 20:
        flood_risk = "⚠️ MEDIUM — Watch for flooding"
    else:
        flood_risk = "✅ LOW — No flood risk"

    if rain_total > 20:
        advice = "🌧️ Heavy rain expected! Delay irrigation & spraying."
    elif rain_total > 5:
        advice = "☁️ Light rain expected — prepare drainage."
    else:
        advice = "☀️ No rain — plan irrigation accordingly."

    if avg_temp < 20:
        crop = "Good for wheat, mustard, chickpea."
    elif 20 <= avg_temp <= 30:
        crop = "Suitable for cotton, paddy, maize."
    else:
        crop = "Too hot — use heat-tolerant crops."

    return flood_risk, advice, crop, avg_temp, avg_humidity

# ---------- Main Display ----------
st.title("🌦️ " + translate_text("Rain Forecast", language))

city_list = [city.strip()] + [a.strip() for a in areas.split(",") if a.strip()]

for c in city_list:
    st.markdown(f"## 📍 {translate_text('City', language)}: **{c}**")
    df = get_weather_forecast(c)

    if df is None or df.empty:
        st.error(f"❌ No forecast found for {c}.")
        continue

    flood_risk, advice, crop, avg_temp, avg_humidity = analyze_forecast(df)

    st.metric("🌡️ Avg Temp (°C)", f"{avg_temp:.1f}")
    st.metric("💧 Avg Humidity (%)", f"{avg_humidity:.0f}")
    st.metric("🌧️ Total Rain (mm)", f"{df['Rain (mm)'].sum():.1f}")

    # Chart
    chart = alt.Chart(df).mark_line(point=True).encode(
        x="Date:T",
        y="Rain (mm):Q",
        tooltip=["Date", "Rain (mm)", "Temperature (°C)", "Humidity (%)"]
    ).properties(height=200)
    st.altair_chart(chart, use_container_width=True)

    st.subheader("💧 " + translate_text("Flood Risk", language))
    st.info(flood_risk)

    st.subheader("🌾 " + translate_text("Farmer Advisory", language))
    st.write(advice)

    st.subheader("🌱 " + translate_text("Crop Suggestion", language))
    st.write(crop)

    st.markdown("---")