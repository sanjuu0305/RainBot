import streamlit as st
st.set_page_config(page_title="🌦️ Rain Forecast Pro", layout="wide", page_icon="☔")

import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from googletrans import Translator  # for translation

# ----------------- Folium Safe Import -----------------
_have_folium = False
try:
    import folium
    from streamlit_folium import st_folium
    _have_folium = True
except:
    pass

# ----------------- Translator Setup -----------------
translator = Translator()

# ----------------- Language Selection -----------------
st.sidebar.header("🌐 Language Settings")
lang = st.sidebar.selectbox("Choose Language", ["English", "Hindi", "Gujarati"])

def t(text):
    """Translate text dynamically based on user language."""
    if lang == "English":
        return text
    dest = "hi" if lang == "Hindi" else "gu"
    try:
        return translator.translate(text, dest=dest).text
    except:
        return text  # fallback

# ----------------- App Header -----------------
st.title(t("☔ RainBot"))
st.markdown(t("An AI-powered rain monitoring dashboard for local users (India Edition 🇮🇳)"))

# ----------------- User Inputs -----------------
city = st.text_input(t("🏙️ Enter City Name:"), "Ahmedabad")
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error(t("⚠️ API key missing! Add your OpenWeatherMap API key in Streamlit → Settings → Secrets."))
    st.info(t('Example secrets.toml entry:\n\napi_key = "your_real_openweathermap_api_key"'))
    st.stop()

# ----------------- Fetch Data -----------------
def get_weather_data(city_name):
    """Return (df, lat, lon, error_message) - df is hourly forecast dataframe"""
    try:
        url_forecast = "https://api.openweathermap.org/data/2.5/forecast"
        params = {"q": city_name, "appid": api_key, "units": "metric"}
        res = requests.get(url_forecast, params=params, timeout=10)
        if res.status_code != 200:
            msg = res.json().get("message", res.text)
            return None, None, None, f"API error {res.status_code}: {msg}"

        data = res.json()
        lat = data["city"]["coord"]["lat"]
        lon = data["city"]["coord"]["lon"]

        df = pd.DataFrame([{
            "Datetime": datetime.fromtimestamp(item["dt"]),
            "Temperature (°C)": item["main"]["temp"],
            "Humidity (%)": item["main"]["humidity"],
            "Rain (mm)": item.get("rain", {}).get("3h", 0.0),
            "Weather": item["weather"][0]["description"].capitalize(),
            "Wind (km/h)": round(item["wind"]["speed"] * 3.6, 1)
        } for item in data["list"]])

        df["Date"] = df["Datetime"].dt.date
        return df, lat, lon, None

    except Exception as e:
        return None, None, None, str(e)

data, lat, lon, err = get_weather_data(city)
if err:
    st.error(f"❌ {t(err)}")
    st.stop()

# ----------------- Map View -----------------
st.subheader(t("📍 Rain Intensity Map"))
if _have_folium:
    m = folium.Map(location=[lat, lon], zoom_start=7)
    folium.TileLayer("cartodbpositron").add_to(m)
    folium.Marker([lat, lon], popup=f"{city}", tooltip=f"{city}").add_to(m)
    folium.raster_layers.TileLayer(
        tiles=f"https://tile.openweathermap.org/map/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={api_key}",
        attr="Rain Data © OpenWeatherMap", name="Rainfall", opacity=0.5
    ).add_to(m)
    folium.LayerControl().add_to(m)
    st_folium(m, width=700, height=500)
else:
    st.info(t("Map feature disabled. Please install 'folium' and 'streamlit-folium'."))

# ----------------- Hourly Forecast -----------------
st.subheader(t("🕒 Hourly Forecast (Next 48 Hours)"))
fig_hourly = go.Figure()
fig_hourly.add_trace(go.Bar(x=data["Datetime"], y=data["Rain (mm)"], name="Rain (mm)"))
fig_hourly.add_trace(go.Scatter(x=data["Datetime"], y=data["Temperature (°C)"],
                                name="Temperature (°C)", mode="lines+markers", yaxis="y2"))
fig_hourly.update_layout(
    title=t("Hourly (3-hour step) Rain & Temperature"),
    xaxis_title=t("Time"),
    yaxis=dict(title=t("Rain (mm)")),
    yaxis2=dict(title=t("Temperature (°C)"), overlaying="y", side="right")
)
st.plotly_chart(fig_hourly, use_container_width=True)

# ----------------- 7-Day Summary -----------------
st.subheader(t("📊 7-Day Average Rainfall Summary"))
df_daily = data.groupby("Date").agg({
    "Rain (mm)": "sum",
    "Temperature (°C)": "mean",
    "Humidity (%)": "mean"
}).reset_index()

fig_summary = go.Figure()
fig_summary.add_trace(go.Bar(x=df_daily["Date"], y=df_daily["Rain (mm)"], name="Rain (mm)"))
fig_summary.update_layout(title=t("Daily Rainfall Trend"), xaxis_title=t("Date"), yaxis_title=t("Rain (mm)"))
st.plotly_chart(fig_summary, use_container_width=True)
st.dataframe(df_daily, use_container_width=True)

# ----------------- Flood Risk Index -----------------
st.subheader(t("💧 Real-Time Flood Risk Index"))
avg_rain = df_daily["Rain (mm)"].mean()
avg_humidity = df_daily["Humidity (%)"].mean()

if avg_rain > 20 and avg_humidity > 80:
    flood_risk = t("🚨 HIGH – Flood risk possible!")
elif avg_rain > 10 and avg_humidity > 70:
    flood_risk = t("⚠️ MEDIUM – Watch weather updates.")
else:
    flood_risk = t("✅ LOW – No flood risk.")
st.info(flood_risk)

# ----------------- Telegram Alerts -----------------
st.subheader(t("📲 Rain Alert Notification"))
telegram_token = st.text_input(t("Enter Telegram Bot Token (optional):"), type="password")
chat_id = st.text_input(t("Enter Your Telegram Chat ID (optional):"))

def get_today_rain(df):
    today = datetime.utcnow().date()
    if today in df["Date"].values:
        return df[df["Date"] == today]["Rain (mm)"].sum()
    return 0.0

if st.button(t("Send Rain Alert")):
    if not telegram_token or not chat_id:
        st.warning(t("Please enter both Telegram Bot Token and Chat ID to send alerts."))
    else:
        rain_today = get_today_rain(df_daily)
        msg = f"🌧️ {t('Rain Alert for')} {city}!\n{t('Today’s Rain')}: {rain_today:.2f} mm\n{t('Flood Risk')}: {flood_risk}"
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        resp = requests.post(telegram_url, data={"chat_id": chat_id, "text": msg})
        if resp.status_code == 200:
            st.success(t("✅ Alert sent successfully to your Telegram!"))
        else:
            st.error(f"Telegram API error {resp.status_code}: {resp.text}")