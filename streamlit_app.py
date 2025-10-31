# streamlit_rain_nowcast.py
"""
AI Real-Time Rain Forecast - Streamlit app (scipy-free)
- Uses a pure-NumPy separable Gaussian blur to avoid scipy dependency.
- Mock nowcast + Open-Meteo hourly forecast.
"""

import streamlit as st
import numpy as np
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
import time

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Real-Time Rain Forecast", layout="wide")
st.title("🌧️ AI Real-Time Rain Forecast")
st.caption("Location-based short-term nowcast + hourly forecast (demo). Replace mock nowcast with real model when available.")

# ---------------- Theme ----------------
LIGHT_CSS = "body { background-color: white; color: #111; }"
DARK_CSS = """
body { background-color: #0e1117; color: #e6eef8; }
.stMarkdown, .stText, .stButton { color: #e6eef8; }
"""
theme = st.sidebar.selectbox("Theme", ["Light", "Dark"], index=0)
st.markdown(f"<style>{DARK_CSS if theme == 'Dark' else LIGHT_CSS}</style>", unsafe_allow_html=True)

# ---------------- Sidebar / Settings ----------------
st.sidebar.header("Nowcast settings")
lat = st.sidebar.number_input("Latitude", value=23.0225, format="%.6f")
lon = st.sidebar.number_input("Longitude", value=72.5714, format="%.6f")
cadence_min = st.sidebar.selectbox("Temporal cadence (min)", [1, 5, 10], index=1)
history_frames = st.sidebar.slider("History frames", min_value=6, max_value=24, value=12)
lead_minutes = st.sidebar.slider("Forecast lead (minutes)", min_value=15, max_value=120, value=60, step=15)
run_nowcast = st.sidebar.button("Run Nowcast")
st.sidebar.markdown("---")
st.sidebar.markdown("Data: Open-Meteo (hourly forecast). Nowcast is mocked for demo; replace with your model.")

# ---------------- Helpers ----------------
@st.cache_data(ttl=300)
def geocode_location(name: str):
    try:
        geolocator = Nominatim(user_agent="rain-nowcast-app")
        loc = geolocator.geocode(name, timeout=10)
        if loc:
            return loc.latitude, loc.longitude
    except Exception:
        return None, None
    return None, None

@st.cache_data(ttl=300)
def fetch_hourly_forecast(lat: float, lon: float, hours: int = 72):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&hourly=precipitation,temperature_2m&timezone=UTC"
        )
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json().get("hourly", {})
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
        return df.head(hours)
    except Exception:
        return pd.DataFrame()

# ---------------- NumPy separable Gaussian blur (no scipy) ----------------
def gaussian_kernel1d(sigma, radius=None):
    if sigma <= 0:
        return np.array([1.0], dtype=np.float32)
    if radius is None:
        radius = int(3.0 * sigma)
    x = np.arange(-radius, radius + 1)
    k = np.exp(-(x ** 2) / (2 * sigma * sigma))
    k = k / k.sum()
    return k.astype(np.float32)

def convolve_1d_along_axis(arr, kernel, axis):
    """Convolve 1D kernel along given axis using np.apply_along_axis + np.convolve(mode='same')."""
    def conv1d(v):
        return np.convolve(v, kernel, mode="same")
    return np.apply_along_axis(conv1d, axis, arr)

def gaussian_blur_numpy(img, sigma=1.0):
    """
    Separable Gaussian blur implemented with NumPy.
    img: 2D array
    sigma: standard deviation
    """
    if sigma <= 0:
        return img
    kernel = gaussian_kernel1d(sigma)
    # convolve rows then cols (separable)
    tmp = convolve_1d_along_axis(img, kernel, axis=1)
    out = convolve_1d_along_axis(tmp, kernel, axis=0)
    return out

# ---------------- Mock radar/model functions ----------------
@st.cache_data(ttl=30)
def fetch_mock_radar_frames(lat, lon, frames=12, H=128, W=128):
    rng = np.random.default_rng(seed=abs(int((lat + lon) * 1e4)) % 2**31)
    base = rng.random((frames, H, W)) * 0.12
    for t in range(frames):
        cx = int(H * 0.3 + t * 0.6)
        cy = int(W * 0.4 + t * 0.9)
        rr = 10
        Y, X = np.ogrid[:H, :W]
        mask = ((X - cx) ** 2 + (Y - cy) ** 2) <= rr * rr
        base[t][mask] += 0.75 * np.exp(-t / frames)
    return np.clip(base, 0.0, 1.0).astype("float32")

def run_mock_nowcast(frames_array, leads=12):
    frames, H, W = frames_array.shape
    out = np.zeros((leads, H, W), dtype="float32")
    last = frames_array[-1]
    for i in range(leads):
        shift = (i * 2) % W
        advected = np.roll(last, shift=shift, axis=1)
        out[i] = gaussian_blur_numpy(advected, sigma=1 + i * 0.15)
    return np.clip(out, 0.0, 1.0)

# ---------------- Layout ----------------
left, right = st.columns([2, 1])

with left:
    st.subheader("Location")
    location_input = st.text_input("Enter place name (village / city / district). Leave empty to use numeric coords from sidebar.")
    if location_input:
        lat_g, lon_g = geocode_location(location_input)
        if lat_g is None:
            st.error("Could not find location. Try a more specific name or use lat/lon in the sidebar.")
        else:
            st.success(f"Found: {location_input} → ({lat_g:.6f}, {lon_g:.6f})")
            lat, lon = lat_g, lon_g

    st.subheader("Hourly Forecast (Open-Meteo)")
    df_hourly = fetch_hourly_forecast(lat, lon, hours=72)
    if df_hourly.empty:
        st.info("Hourly forecast not available or Open-Meteo unreachable.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_hourly.index,
            y=df_hourly["precipitation"],
            name="Precip (mm)",
            marker_color="rgba(0,120,255,0.4)"
        ))
        fig.add_trace(go.Scatter(
            x=df_hourly.index,
            y=df_hourly["temperature_2m"],
            name="Temp (°C)",
            yaxis="y2",
            line=dict(color="orange")
        ))
        fig.update_layout(
            title="Hourly Precipitation & Temperature (UTC)",
            xaxis_title="Time (UTC)",
            yaxis=dict(title="Precipitation (mm)"),
            yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right"),
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Nowcast (short-term, demo)")
    st.write(f"Using last {history_frames} frames at {cadence_min} min cadence → lead {lead_minutes} min")

    if run_nowcast:
        t_start = time.time()
        frames_arr = fetch_mock_radar_frames(lat, lon, frames=history_frames, H=128, W=128)
        leads = max(1, lead_minutes // cadence_min)
        prob_maps = run_mock_nowcast(frames_arr, leads=leads)

        # show last 3 frames
        st.markdown("Recent radar frames (mock):")
        cols = st.columns(3)
        last3 = frames_arr[-3:]
        for i, c in enumerate(cols):
            with c:
                st.image((last3[i] * 255).astype("uint8"), clamp=True, use_column_width=True, caption=f"t-{3-i}")

        # show nowcast lead maps (early, mid, last)
        st.markdown("Nowcast probability maps (sample leads):")
        idxs = [0, max(0, leads // 2), leads - 1]
        for idx in idxs:
            st.markdown(f"t+{(idx + 1) * cadence_min} min")
            st.image((prob_maps[idx] * 255).astype("uint8"), clamp=True, use_column_width=True)

        # center-point forecast
        px, py = prob_maps.shape[1] // 2, prob_maps.shape[2] // 2
        center_probs = [float(prob_maps[i, px, py]) for i in range(prob_maps.shape[0])]
        avg_prob = float(np.mean(center_probs))
        st.metric(label=f"Chance of rain (avg next {lead_minutes} min)", value=f"{avg_prob*100:.1f}%")

        # combine timeline with hourly forecast if available
        if not df_hourly.empty:
            now_utc = pd.Timestamp.utcnow().floor(f"{cadence_min}min")
            lead_times = [now_utc + pd.Timedelta(minutes=(i + 1) * cadence_min) for i in range(len(center_probs))]
            timeline_df = pd.DataFrame({"time": lead_times, "nowcast_prob": center_probs}).set_index("time")

            end_time = lead_times[-1]
            precip_slice = df_hourly["precipitation"].loc[(df_hourly.index >= now_utc) & (df_hourly.index <= end_time)]
            if precip_slice.empty:
                precip_slice = df_hourly["precipitation"].head(len(lead_times))

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=precip_slice.index,
                y=precip_slice.values,
                name="Forecast precip (mm)",
                yaxis="y2",
                marker_color="rgba(0,150,255,0.4)"
            ))
            fig2.add_trace(go.Scatter(
                x=timeline_df.index,
                y=timeline_df["nowcast_prob"],
                mode="lines+markers",
                name="Nowcast P(rain)",
                yaxis="y1",
                line=dict(width=2, color="crimson")
            ))
            fig2.update_layout(
                title="Nowcast probability vs Hourly forecast precipitation",
                xaxis_title="Time (UTC)",
                yaxis=dict(title="Nowcast probability", range=[0,1]),
                yaxis2=dict(title="Precipitation (mm)", overlaying="y", side="right"),
                template="plotly_white"
            )
            st.plotly_chart(fig2, use_container_width=True)

        # optional alert
        if avg_prob >= 0.6:
            st.error(f"⚠️ High chance of rain in next {lead_minutes} minutes: {avg_prob*100:.0f}%")
        elif avg_prob >= 0.3:
            st.warning(f"Possible rain: {avg_prob*100:.0f}%")
        else:
            st.success("Low chance of rain in the immediate window.")

        st.write({
            "lat": lat,
            "lon": lon,
            "lead_minutes": lead_minutes,
            "runtime_s": round(time.time() - t_start, 2)
        })
    else:
        st.info("Set parameters in sidebar and click **Run Nowcast** to generate a demo prediction.")

with right:
    st.subheader("Quick controls")
    st.write("• Update location using the text box on the left (optional).")
    st.write("• Use the numeric lat/lon in the sidebar for precise coords.")
    st.markdown("---")
    st.subheader("Notes")
    st.write("- This demo uses a **mock nowcast** (advection + separable NumPy Gaussian blur). Replace `fetch_mock_radar_frames()` and `run_mock_nowcast()` with real radar ingestion + model inference.")
    st.write("- Open-Meteo provides hourly forecast precipitation used to compare with nowcast probability.")
    st.write("- Times shown are in **UTC**.")

# End of file