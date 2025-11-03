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
st.sidebar.header("🌐 Choose language / ભાષા પસંદ કરો")
language = st.sidebar.selectbox("Language", ["English", "Hindi", "Gujarati"])

def translate_text(text, lang=None):
    """
    Translate short UI text using deep-translator (Google).
    Accepts an optional lang argument; defaults to the global `language`.
    If translation fails, returns the original text.
    """
    if lang is None:
        lang = language
    if lang == "English":
        return text
    target = "hi" if lang == "Hindi" else "gu"
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        # fallback: return original text
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

    # ----------------- Radar & overlay map (RainViewer + OpenWeatherMap tiles) -----------------
    st.subheader(translate_text("📡 Radar / Layers"))
    st.write(translate_text("Tip: use the layer control to toggle overlays."))

    if _have_folium:
        # 1) Fetch available radar timestamps from RainViewer
        try:
            rv_info = requests.get("https://api.rainviewer.com/public/maps.json", timeout=8).json()
            timestamps = rv_info.get("radar", {}).get("past", [])
            rv_times = [int(t) for t in timestamps] if timestamps else []
        except Exception:
            rv_info = None
            rv_times = []

        # 2) UI controls: choose overlay layer and (if radar) choose time index
        layer_choice = st.selectbox(
            translate_text("Select map layer"),
            ["None", "RainViewer Radar", "OWM Precipitation", "OWM Clouds"]
        )

        # If RainViewer selected, let user pick a time frame (latest by default)
        if layer_choice == "RainViewer Radar" and rv_times:
            idx = st.slider(
                translate_text("Radar frame (past)"),
                min_value=0, max_value=len(rv_times)-1, value=len(rv_times)-1, step=1
            )
            selected_time = rv_times[idx]
        else:
            selected_time = None

        # 3) Build folium map and add base + overlays
        try:
            m = folium.Map(location=[lat, lon], zoom_start=8, control_scale=True)
            folium.TileLayer("cartodbpositron", name="Base Map").add_to(m)

            # OpenWeatherMap tiles (requires api_key)
            owm_key = api_key  # ensure this is set earlier in your app
            if layer_choice == "OWM Precipitation" and owm_key:
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.openweathermap.org/map/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={owm_key}",
                    attr="Precipitation © OpenWeatherMap",
                    name="OWM Precipitation",
                    opacity=0.6
                ).add_to(m)
            if layer_choice == "OWM Clouds" and owm_key:
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.openweathermap.org/map/clouds_new/{{z}}/{{x}}/{{y}}.png?appid={owm_key}",
                    attr="Clouds © OpenWeatherMap",
                    name="OWM Clouds",
                    opacity=0.6
                ).add_to(m)

            # RainViewer Radar overlay (single time frame)
            if layer_choice == "RainViewer Radar" and selected_time:
                folium.raster_layers.TileLayer(
                    tiles=f"https://tile.rainviewer.com/v2/radar/{selected_time}/{{z}}/{{x}}/{{y}}.png",
                    attr="Radar © RainViewer",
                    name=f"RainViewer Radar ({datetime.utcfromtimestamp(selected_time).strftime('%Y-%m-%d %H:%M UTC')})",
                    opacity=0.6
                ).add_to(m)

            # Add marker for the chosen location
            folium.CircleMarker([lat, lon], radius=6, color="blue", fill=True, fill_opacity=0.9, popup=city).add_to(m)

            # Layer control to toggle overlays
            folium.LayerControl().add_to(m)

            # Render in Streamlit
            st_data = st_folium(m, width=800, height=450)
        except Exception as e:
            st.warning(translate_text("Map could not be rendered. Showing basic map instead."))
            st.write(f":information_source: Map error: {e}")
            st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))
    else:
        st.info(translate_text("Map feature disabled. Please install 'folium' and 'streamlit-folium'."))
        if _folium_import_error:
            st.write(f":information_source: Folium import error: {_folium_import_error}")
        st.map(pd.DataFrame({"lat":[lat],"lon":[lon]}))

    # ----------------- (Telegram removed) -----------------
    # The Telegram alert section has been removed as requested.
    # If you want another alert channel (email / SMS / webhook), I can add it here.

    # ----------------- Footer / tips -----------------
    st.markdown("---")
    st.write(translate_text("Tips:"))
    st.write("- " + translate_text("For best results, include the correct city name (City, State or City, Country)."))
    st.write("- " + translate_text("Use the map layers to visualize radar & precipitation overlays."))