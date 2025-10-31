import streamlit as st
st.set_page_config(page_title="🌦️ Rain Forecast Pro", layout="wide", page_icon="☔")

import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from deep_translator import GoogleTranslator

# Optional folium imports
_have_folium = False
_folium_import_error = None
try:
    import folium
    from streamlit_folium import st_folium
    _have_folium = True
except Exception as e:
    _folium_import_error = e

# ----------------- Sidebar: Language Selector -----------------
st.sidebar.header("🌐 Choose language / भाषा પસંદ કરો")
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])

def translate_text(text):
    """Translate short UI text using deep-translator (Google)."""
    if language == "English":
        return text
    target = "hi" if language == "Hindi" else "gu"
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        # if translation fails, return original text
        return text

# ----------------- Header -----------------
st.title(translate_text("🌦️ Rain Forecast Dashboard"))
st.markdown(translate_text("Enter your city name to see past & forecast rainfall, flood risk and alerts."))

# ----------------- API key (use secrets) -----------------
# Put your OpenWeatherMap API key in Streamlit Secrets as: openweather_api_key = "YOUR_KEY"
api_key = st.secrets.get("openweather_api_key", "")
if not api_key:
    st.error(translate_text("API key missing. Add 'openweather_api_key' in Streamlit Secrets."))
    st.info('Example (Streamlit Secrets):\n\nopenweather_api_key = "your_openweathermap_api_key_here"')
    st.stop()

# ----------------- Input -----------------
city = st.text_input(translate_text("Enter city name:"), "Ahmedabad")

# ----------------- Geocoding using OpenWeatherMap (reliable) -----------------
def geocode_city(city_name):
    geo_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city_name, "limit": 1, "appid": api_key}
    try:
        r = requests.get(geo_url, params=params, timeout=10)
        if r.status_code != 200:
            return None, None, f"Geocoding API error {r.status_code}: {r.text}"
        data = r.json()
        if not data:
            return None, None, "No geocoding result"
        lat = data[0]["lat"]
        lon = data[0]["lon"]
        return lat, lon, None
    except requests.exceptions.RequestException as e:
        return None, None, f"Network/geocode error: {e}"

# ----------------- Fetch forecast data -----------------
def fetch_forecast_by_latlon(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, f"Forecast API error {r.status_code}: {r.text}"
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Network/forecast error: {e}"

# ----------------- Helper to build DataFrame -----------------
def build_forecast_df(forecast_json):
    items = forecast_json.get("list", [])
    rows = []
    for it in items:
        dt = datetime.fromtimestamp(it.get("dt", 0))
        temp = it.get("main", {}).get("temp")
        hum = it.get("main", {}).get("humidity")
        rain = it.get("rain", {}).get("3h", 0.0) if it.get("rain") else 0.0
        cond = it.get("weather", [{}])[0].get("description", "").capitalize()
        wind = round(it.get("wind", {}).get("speed", 0.0) * 3.6, 1)
        rows.append({"Datetime": dt, "Date": dt.date(), "Temperature (°C)": temp,
                     "Humidity (%)": hum, "Rain (mm)": rain, "Condition": cond, "Wind (km/h)": wind})
    df = pd.DataFrame(rows)
    return df

# ----------------- Main flow -----------------
if city:
    with st.spinner(translate_text("Finding location...")):
        lat, lon, geo_err = geocode_city(city)
    if geo_err:
        st.error(translate_text("City not found or geocode failed: ") + f" {geo_err}")
        st.stop()

    with st.spinner(translate_text("Fetching forecast...")):
        forecast_json, forecast_err = fetch_forecast_by_latlon(lat, lon)
    if forecast_err:
        st.error(translate_text("Could not fetch forecast: ") + f"{forecast_err}")
        st.stop()

    # Build dataframe
    df = build_forecast_df(forecast_json)
    if df.empty:
        st.error(translate_text("No forecast data available."))
        st.stop()

    # Hourly (3-hour step) chart
    st.subheader(translate_text("🕒 Hourly Rain & Temperature (3-hour steps)"))
    fig_h = go.Figure()
    fig_h.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name=translate_text("Rain (mm)"), marker_color="skyblue"))
    fig_h.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"], name=translate_text("Temperature (°C)"),
                               mode="lines+markers", yaxis="y2"))
    fig_h.update_layout(title=translate_text("Hourly Rain & Temperature"),
                        xaxis_title=translate_text("Time"),
                        yaxis=dict(title=translate_text("Rain (mm)")),
                        yaxis2=dict(title=translate_text("Temperature (°C)"), overlaying="y", side="right"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    st.plotly_chart(fig_h, use_container_width=True)

    # 7-day daily summary
    st.subheader(translate_text("📊 Daily Rain Summary (available forecast days)"))
    df_daily = df.groupby("Date").agg({
        "Rain (mm)": "sum",
        "Temperature (°C)": "mean",
        "Humidity (%)": "mean"
    }).reset_index().sort_values("Date")
    st.dataframe(df_daily, use_container_width=True)

    # 7-day chart
    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(x=df_daily["Date"], y=df_daily["Rain (mm)"], name=translate_text("Rain (mm)"), marker_color="deepskyblue"))
    fig_d.update_layout(title=translate_text("Daily Rainfall Trend"), xaxis_title=translate_text("Date"), yaxis_title=translate_text("Rain (mm)"))
    st.plotly_chart(fig_d, use_container_width=True)

    # Flood risk heuristic
    st.subheader(translate_text("💧 Flood Risk Index (simple heuristic)"))
    avg_rain = float(df_daily["Rain (mm)"].mean()) if not df_daily.empty else 0.0
    avg_hum = float(df_daily["Humidity (%)"].mean()) if not df_daily.empty else 0.0
    if avg_rain > 20 and avg_hum > 80:
        flood_text = translate_text("HIGH — Flood risk possible")
        color = "red"
    elif avg_rain > 10 and avg_hum > 70:
        flood_text = translate_text("MEDIUM — Watch updates")
        color = "orange"
    else:
        flood_text = translate_text("LOW — No flood risk")
        color = "green"
    st.markdown(f"<div style='padding:10px;border-radius:6px;background-color:#f7fbff'><b style='color:{color}'>{flood_text}</b></div>", unsafe_allow_html=True)

    # Map: folium if available, else st.map
    st.subheader(translate_text("📍 Map View"))
    if _have_folium:
        try:
            m = folium.Map(location=[lat, lon], zoom_start=9)
            folium.Marker([lat, lon], popup=city, tooltip=city).add_to(m)
            # Add OWM precipitation tiles (requires api_key)
            folium.raster_layers.TileLayer(
                tiles=f"https://tile.openweathermap.org/map/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={api_key}",
                attr="OpenWeatherMap precipitation", name="Precipitation", opacity=0.5
            ).add_to(m)
            folium.LayerControl().add_to(m)
            st_folium(m, width=800, height=450)
        except Exception as e:
            st.info(translate_text("Map failed to render; showing basic map instead."))
            st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))
    else:
        # fallback
        st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))
        if _folium_import_error:
            st.info(translate_text("To enable a nicer map add 'folium' and 'streamlit-folium' to requirements."))

    # ----------------- Telegram alert (optional) -----------------
    st.subheader(translate_text("📲 Rain Alert (Telegram)"))
    st.write(translate_text("Enter bot token and chat id to send a test alert (optional)."))
    telegram_token = st.text_input(translate_text("Telegram Bot Token (optional)"), type="password")
    chat_id = st.text_input(translate_text("Telegram Chat ID (optional)"))

    def today_rain_value(df_daily):
        today = datetime.utcnow().date()
        if today in df_daily["Date"].values:
            return float(df_daily[df_daily["Date"]==today]["Rain (mm)"].sum())
        # fallback: nearest day or 0
        return float(df_daily["Rain (mm)"].iloc[0]) if not df_daily.empty else 0.0

    if st.button(translate_text("Send Test Alert")):
        if not telegram_token or not chat_id:
            st.warning(translate_text("Please provide both Telegram token and chat id."))
        else:
            rain_today = today_rain_value(df_daily)
            # translate alert message based on language
            alert_msg_en = f"🌧️ Rain Alert for {city}! Today's Rain: {rain_today:.2f} mm. Flood Risk: {flood_text}"
            alert_msg = alert_msg_en if language == "English" else translate_text(alert_msg_en)
            try:
                resp = requests.post(f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                                     data={"chat_id": chat_id, "text": alert_msg}, timeout=10)
                if resp.status_code == 200:
                    st.success(translate_text("Alert sent successfully!"))
                else:
                    st.error(translate_text("Telegram API error: ") + f"{resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(translate_text("Failed to send Telegram message: ") + str(e))