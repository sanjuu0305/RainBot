import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from deep_translator import GoogleTranslator

# Optional folium imports (for live rain map)
_have_folium = False
try:
    import folium
    from streamlit_folium import st_folium
    _have_folium = True
except Exception as e:
    _folium_import_error = e

# ---------------- CONFIG ----------------
st.set_page_config(page_title="🌾 Farmer Advisor Bot", page_icon="🌦️", layout="wide")

st.sidebar.header("🌐 Choose language / ભાષા પસંદ કરો")
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])

def translate_text(text):
    """Translate short text via deep_translator (Google)."""
    if language == "English":
        return text
    target = "hi" if language == "Hindi" else "gu"
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        return text

st.title(translate_text("🌾 Farmer Advisor Bot"))
st.markdown(translate_text("Real-time rain forecast, flood alerts, and smart farming suggestions."))

# ---------------- API ----------------
api_key = st.secrets.get("openweather_api_key", "")
if not api_key:
    st.error(translate_text("API key missing. Add it to Streamlit Secrets as 'openweather_api_key'."))
    st.stop()

# ---------------- Input ----------------
city = st.text_input(translate_text("Enter your city name:"), "Surat")

# ---------------- Geocode City ----------------
def geocode_city(city_name):
    geo_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city_name, "limit": 1, "appid": api_key}
    try:
        r = requests.get(geo_url, params=params, timeout=10)
        data = r.json()
        if not data:
            return None, None
        return data[0]["lat"], data[0]["lon"]
    except:
        return None, None

# ---------------- Fetch Forecast ----------------
def fetch_forecast(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

# ---------------- Build DataFrame ----------------
def build_forecast_df(forecast_json):
    rows = []
    for it in forecast_json.get("list", []):
        dt = datetime.fromtimestamp(it["dt"])
        temp = it["main"]["temp"]
        hum = it["main"]["humidity"]
        rain = it.get("rain", {}).get("3h", 0)
        cond = it["weather"][0]["description"].capitalize()
        rows.append({
            "Datetime": dt, "Date": dt.date(),
            "Temperature (°C)": temp, "Humidity (%)": hum,
            "Rain (mm)": rain, "Condition": cond
        })
    return pd.DataFrame(rows)

# ---------------- Advisory Logic ----------------
def farming_advice(avg_rain, avg_temp, avg_hum):
    if avg_rain > 30:
        return "🚨 Heavy rain expected — avoid fertilizer, protect stored grains."
    elif 10 < avg_rain <= 30:
        return "🌧️ Moderate rain — irrigation not needed, prepare drainage."
    elif avg_rain <= 10 and avg_temp > 30:
        return "☀️ Dry & hot — irrigate crops early morning or evening."
    elif avg_temp < 20:
        return "❄️ Cool weather — suitable for wheat and chickpea crops."
    elif 20 <= avg_temp <= 30:
        return "🌱 Ideal for cotton, paddy, maize. Maintain soil moisture."
    else:
        return "🌾 Normal conditions — continue routine farming activities."

# ---------------- Main Execution ----------------
if city:
    lat, lon = geocode_city(city)
    if not lat:
        st.error(translate_text("Could not find city. Try again."))
        st.stop()

    forecast_json = fetch_forecast(lat, lon)
    if not forecast_json:
        st.error(translate_text("Unable to fetch forecast data."))
        st.stop()

    df = build_forecast_df(forecast_json)
    if df.empty:
        st.warning(translate_text("No forecast data available."))
        st.stop()

    # Charts
    st.subheader(translate_text("🌦️ Hourly Rain & Temperature (3-hour steps)"))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Datetime"], y=df["Rain (mm)"], name=translate_text("Rain (mm)"), marker_color="skyblue"))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Temperature (°C)"], mode="lines+markers",
                             name=translate_text("Temperature (°C)"), yaxis="y2"))
    fig.update_layout(
        yaxis=dict(title=translate_text("Rain (mm)")),
        yaxis2=dict(title=translate_text("Temperature (°C)"), overlaying="y", side="right"),
        xaxis_title=translate_text("Time"),
        legend=dict(orientation="h", y=1.05),
        title=translate_text("Rainfall & Temperature Trend")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Daily summary
    df_daily = df.groupby("Date").agg({
        "Rain (mm)": "sum",
        "Temperature (°C)": "mean",
        "Humidity (%)": "mean"
    }).reset_index()

    st.subheader(translate_text("📅 Daily Rain Summary"))
    st.dataframe(df_daily, use_container_width=True)

    # Risk analysis
    avg_rain = df_daily["Rain (mm)"].mean()
    avg_temp = df_daily["Temperature (°C)"].mean()
    avg_hum = df_daily["Humidity (%)"].mean()

    if avg_rain > 20 and avg_hum > 80:
        flood_risk = translate_text("🚨 HIGH — Flood risk likely")
        color = "red"
    elif avg_rain > 10:
        flood_risk = translate_text("⚠️ MEDIUM — Stay alert")
        color = "orange"
    else:
        flood_risk = translate_text("✅ LOW — No flood risk")
        color = "green"

    st.markdown(f"<div style='padding:10px;background:#f8f9fa;border-left:5px solid {color};'><b>{flood_risk}</b></div>", unsafe_allow_html=True)

    # Farming advice
    st.subheader(translate_text("👨‍🌾 Smart Farmer Advice"))
    advice = farming_advice(avg_rain, avg_temp, avg_hum)
    st.success(translate_text(advice))

    # Optional: Live rain map
    st.subheader(translate_text("📡 Live Rain Map"))
    if _have_folium:
        m = folium.Map(location=[lat, lon], zoom_start=8, control_scale=True)
        folium.TileLayer("cartodbpositron", name="Base Map").add_to(m)
        folium.raster_layers.TileLayer(
            tiles=f"https://tile.openweathermap.org/map/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={api_key}",
            attr="Precipitation © OpenWeatherMap", name="Rain Layer", opacity=0.6
        ).add_to(m)
        folium.LayerControl().add_to(m)
        folium.Marker([lat, lon], tooltip=city).add_to(m)
        st_folium(m, width=800, height=450)
    else:
        st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

st.markdown("---")
st.caption(translate_text("Developed as part of an AI-based Rain Forecast & Farmer Advisory System 🌾"))