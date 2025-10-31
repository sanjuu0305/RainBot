import streamlit as st
st.set_page_config(page_title="🌦️ Rain Forecast Pro", layout="wide", page_icon="☔")

# Other imports
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Safe optional imports (folium / streamlit_folium). Import after set_page_config.
_have_folium = False
_folium_import_error = None
try:
    import folium
    from streamlit_folium import st_folium
    _have_folium = True
except Exception as e:
    _folium_import_error = e

# App header
st.title("☔ Rain Forecast Pro – Weather, Alerts & Flood Risk")
st.markdown("An AI-powered rain monitoring dashboard 🌧️ for local users (India Edition 🇮🇳)")

# ----------------- User Inputs -----------------
city = st.text_input("🏙️ Enter City Name:", "Ahmedabad")
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error("⚠️ API key missing! Add your OpenWeatherMap API key in Streamlit → Settings → Secrets.")
    st.info('Example secrets.toml entry:\n\napi_key = "your_real_openweathermap_api_key"')
    st.stop()

# ----------------- Fetch Data -----------------
def get_weather_data(city_name):
    """Return (df, lat, lon, error_message) - df is hourly forecast dataframe"""
    try:
        url_forecast = "https://api.openweathermap.org/data/2.5/forecast"
        params = {"q": city_name, "appid": api_key, "units": "metric"}
        res = requests.get(url_forecast, params=params, timeout=10)
        if res.status_code != 200:
            # try to show api message if available
            try:
                msg = res.json().get("message", res.text)
            except Exception:
                msg = res.text
            return None, None, None, f"API error {res.status_code}: {msg}"

        data = res.json()
        city_info = data.get("city", {})
        coord = city_info.get("coord", {})
        lat = coord.get("lat")
        lon = coord.get("lon")
        if lat is None or lon is None:
            return None, None, None, "Coordinates not found for this city."

        forecast_list = data.get("list", [])
        if not forecast_list:
            return None, lat, lon, "No forecast data returned."

        df = pd.DataFrame([{
            "Datetime": datetime.fromtimestamp(item.get("dt", 0)),
            "Temperature (°C)": item.get("main", {}).get("temp", None),
            "Humidity (%)": item.get("main", {}).get("humidity", None),
            "Rain (mm)": item.get("rain", {}).get("3h", 0.0) if item.get("rain") else 0.0,
            "Weather": item.get("weather", [{}])[0].get("description", "").capitalize(),
            "Wind (km/h)": round(item.get("wind", {}).get("speed", 0.0) * 3.6, 1)
        } for item in forecast_list])

        df["Date"] = df["Datetime"].dt.date
        return df, lat, lon, None

    except requests.exceptions.RequestException as e:
        return None, None, None, f"Network error: {e}"
    except Exception as e:
        return None, None, None, f"Unexpected error: {e}"

# Get data
data, lat, lon, err = get_weather_data(city)
if err:
    st.error(f"❌ {err}")
    st.stop()

# ----------------- Map View (only if folium available) -----------------
st.subheader("📍 Rain Intensity Map")
if _have_folium:
    try:
        m = folium.Map(location=[lat, lon], zoom_start=7)
        folium.TileLayer("cartodbpositron").add_to(m)
        folium.Marker([lat, lon], popup=f"{city}", tooltip=f"{city}").add_to(m)
        # precipitation tile from OpenWeatherMap (requires API key)
        folium.raster_layers.TileLayer(
            tiles="https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=" + api_key,
            attr="Rain Data © OpenWeatherMap",
            name="Rainfall",
            opacity=0.5
        ).add_to(m)
        folium.LayerControl().add_to(m)
        st_data = st_folium(m, width=700, height=500)
    except Exception as e:
        st.warning("Map could not be rendered. See logs for details.")
        st.write(f":information_source: Map error: {e}")
else:
    st.info("Map feature disabled. Add `folium` and `streamlit-folium` to requirements.txt and restart the app.")
    if _folium_import_error:
        # show short hint (avoid sensitive stacktrace)
        st.write(f":information_source: Folium import error: {_folium_import_error}")

# ----------------- Hourly Forecast -----------------
st.subheader("🕒 Hourly Forecast (Next 48 Hours)")
try:
    # Show next 48 hours (forecast provides 3-hour steps -> about 5-6 days)
    # We'll show available hourly-like (3h) data present in 'data'
    fig_hourly = go.Figure()
    fig_hourly.add_trace(go.Bar(x=data["Datetime"], y=data["Rain (mm)"], name="Rain (mm)"))
    fig_hourly.add_trace(go.Scatter(x=data["Datetime"], y=data["Temperature (°C)"],
                                   name="Temperature (°C)", mode="lines+markers", yaxis="y2"))
    fig_hourly.update_layout(
        title="Hourly (3-hour step) Rain & Temperature",
        xaxis_title="Time",
        yaxis=dict(title="Rain (mm)"),
        yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right")
    )
    st.plotly_chart(fig_hourly, use_container_width=True)
except Exception as e:
    st.warning("Could not render hourly chart.")
    st.write(f":information_source: Chart error: {e}")

# ----------------- 7-Day Average Summary -----------------
st.subheader("📊 7-Day Average Rainfall Summary (Available Forecast Days)")
try:
    df_daily = data.groupby("Date").agg({
        "Rain (mm)": "sum",
        "Temperature (°C)": "mean",
        "Humidity (%)": "mean"
    }).reset_index().sort_values("Date")

    fig_summary = go.Figure()
    fig_summary.add_trace(go.Bar(x=df_daily["Date"], y=df_daily["Rain (mm)"], name="Rain (mm)"))
    fig_summary.update_layout(title="Daily Rainfall Trend", xaxis_title="Date", yaxis_title="Rain (mm)")
    st.plotly_chart(fig_summary, use_container_width=True)
    st.dataframe(df_daily, use_container_width=True)
except Exception as e:
    st.warning("Could not create daily summary.")
    st.write(f":information_source: Summary error: {e}")

# ----------------- Flood Risk Index -----------------
st.subheader("💧 Real-Time Flood Risk Index (Simple Heuristic)")
try:
    # If df_daily has fewer days, use what we have
    avg_rain = float(df_daily["Rain (mm)"].mean()) if not df_daily.empty else 0.0
    avg_humidity = float(df_daily["Humidity (%)"].mean()) if not df_daily.empty else 0.0

    if avg_rain > 20 and avg_humidity > 80:
        flood_risk = "🚨 HIGH – Flood risk possible! (ભારે વરસાદની શક્યતા)"
    elif avg_rain > 10 and avg_humidity > 70:
        flood_risk = "⚠️ MEDIUM – Watch weather updates. (મધ્યમ વરસાદ)"
    else:
        flood_risk = "✅ LOW – No flood risk. (સુરક્ષિત સ્થિતિ)"

    st.info(flood_risk)
except Exception as e:
    st.warning("Could not compute flood risk.")
    st.write(f":information_source: Flood risk error: {e}")

# ----------------- Rain Alert via Telegram -----------------
st.subheader("📲 Rain Alert Notification")
st.markdown("You can get daily rain alerts on Telegram using your bot token and chat ID.")

telegram_token = st.text_input("Enter Telegram Bot Token (optional):", type="password")
chat_id = st.text_input("Enter Your Telegram Chat ID (optional):")

def get_today_rain(df):
    today = datetime.utcnow().date()
    if today in list(df["Date"]):
        row = df[df["Date"] == today]
        if not row.empty:
            return float(row.iloc[0]["Rain (mm)"])
    # fallback: use first forecast day or 0
    return float(df["Rain (mm)"].iloc[0]) if not df.empty else 0.0

if st.button("Send Rain Alert"):
    if not telegram_token or not chat_id:
        st.warning("Please enter both Telegram Bot Token and Chat ID to send alerts.")
    else:
        try:
            rain_today = get_today_rain(df_daily)
            alert_msg = f"🌧️ Rain Alert for {city}!\nToday's Rain: {rain_today:.2f} mm\nFlood Risk: {flood_risk}"
            telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            resp = requests.post(telegram_url, data={"chat_id": chat_id, "text": alert_msg}, timeout=10)
            if resp.status_code == 200:
                st.success("✅ Alert sent successfully to your Telegram!")
            else:
                st.error(f"Telegram API error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Failed to send Telegram alert: {e}")