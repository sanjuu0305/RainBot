# streamlit_app.py
import streamlit as st
from streamlit_lottie import st_lottie
import json
from geopy.geocoders import Nominatim
import requests
from datetime import datetime, timedelta
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import time
import os

# Optional ONNX runtime import (only if you plan to use ONNX)
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except Exception:
    ONNX_AVAILABLE = False

# ----------------- Gemini Setup -----------------
# NOTE: You already included an API key in your snippet. Keep secure in environment vars for production.
genai.configure(api_key="AIzaSyA28UIrLIfgi6fTATjQTZueAKpSe-P2FDo")
model = genai.GenerativeModel("models/gemini-1.5-flash")

# ----------------- Load Local Lottie Animation -----------------
def load_lottie_file(filepath: str):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

hello_animation = load_lottie_file("hello_animation.json")  # 👈 Must be in same folder (optional)

# ----------------- Utility Functions -----------------
def get_coordinates(location_name):
    geolocator = Nominatim(user_agent="farm-advisor")
    location = geolocator.geocode(location_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_past_weather(lat, lon):
    end_date = datetime.utcnow().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=9)
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        f"&timezone=auto"
    )
    r = requests.get(url, timeout=10)
    return r.json().get("daily", {})

def get_future_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        f"&forecast_days=10&timezone=auto"
    )
    r = requests.get(url, timeout=10)
    return r.json().get("daily", {})

def get_soil_data(lat, lon):
    try:
        # Sample static soil data. Replace with actual API call if available.
        return {
            "phh2o": 6.5,
            "ocd": 25.3,
            "sand": 45,
            "silt": 30,
            "clay": 25,
            "cec": 18.2
        }
    except:
        return None

def safe_avg(values):
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else 0

def safe_sum(values):
    return sum([v for v in values if v is not None])

def get_advice(location, past_weather, future_weather, soil, user_query, language):
    prompt = f"""
You are a smart agriculture advisor and experienced farmer helping a farmer in {location}.
Speak in {language}. Respond in a short, simple, farmer-friendly tone.

**Past 10 Days:**
- Rain: {safe_sum(past_weather.get('precipitation_sum', [])):.1f} mm
- Avg Max Temp: {safe_avg(past_weather.get('temperature_2m_max', [])):.1f}°C
- Avg Min Temp: {safe_avg(past_weather.get('temperature_2m_min', [])):.1f}°C

**Next 10 Days (Forecast):**
- Rain: {safe_sum(future_weather.get('precipitation_sum', [])):.1f} mm
- Avg Max Temp: {safe_avg(future_weather.get('temperature_2m_max', [])):.1f}°C
- Avg Min Temp: {safe_avg(future_weather.get('temperature_2m_min', [])):.1f}°C

Soil:
- pH: {soil['phh2o']}
- Organic Carbon: {soil['ocd']}
- Texture: {soil['sand']}% sand, {soil['silt']}% silt, {soil['clay']}% clay

Farmer's Question: '{user_query}'
"""
    response = model.generate_content(prompt)
    return response.text.strip()

# ---------------- Nowcast helpers (mock + ONNX support) ----------------
from scipy.ndimage import gaussian_filter

def gaussian_blur(img, sigma=1.0):
    return gaussian_filter(img, sigma=sigma)

@st.cache_data(ttl=30)
def fetch_local_radar_frames_mock(lat, lon, frames=12, H=128, W=128):
    """
    Mocked radar frames: returns (frames, H, W) float32 array with values 0..1.
    Replace with real local radar ingestion (FTP/HTTP or local disk).
    """
    rng = np.random.default_rng(seed=abs(int((lat+lon)*1e4)) % 2**31)
    base = rng.random((frames, H, W)) * 0.15
    # add a moving 'cell' to simulate precipitation
    for t in range(frames):
        cx = int(H*0.3 + t*0.6)
        cy = int(W*0.4 + t*0.9)
        rr = 10
        Y, X = np.ogrid[:H, :W]
        mask = ((X-cx)**2 + (Y-cy)**2) <= rr*rr
        base[t][mask] += 0.7 * np.exp(-t/frames)
    return np.clip(base, 0.0, 1.0).astype('float32')

def run_model_mock(frames_array, leads=12):
    """
    Simple advection + blur mock nowcast. Replace with real model inference.
    Output: (leads, H, W) probabilistic maps (0..1)
    """
    frames, H, W = frames_array.shape
    out = np.zeros((leads, H, W), dtype='float32')
    last = frames_array[-1]
    for i in range(leads):
        shift = (i * 2) % W
        advected = np.roll(last, shift=shift, axis=1)
        out[i] = gaussian_blur(advected, sigma=1 + i*0.15)
    return np.clip(out, 0.0, 1.0)

# ONNX helpers (optional)
def load_onnx_model(path):
    if not ONNX_AVAILABLE:
        raise RuntimeError("onnxruntime not installed. Install onnxruntime to use ONNX model.")
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    return sess

def run_onnx_inference(sess, frames_array):
    """
    Example wrapper: adapt input preprocessing / axis order to your ONNX model's expectations.
    Assumes model expects shape (1, C, T, H, W) or similar; change accordingly.
    """
    inp = frames_array.astype('float32')[None, None, ...]  # (1,1,T,H,W)
    out = sess.run(None, {sess.get_inputs()[0].name: inp})
    # Expecting an output like (1, leads, H, W)
    out_arr = np.array(out[0])
    if out_arr.ndim == 4:
        return out_arr[0]  # (leads, H, W)
    # adapt as needed
    return out_arr.squeeze()

# ----------------- Streamlit UI -----------------
st.set_page_config(page_title="AI Agent for Agriculture + Local Nowcast", layout="wide")
# Header
st.markdown("""
    <div style='display:flex;align-items:center;justify-content:space-between'>
      <div>
        <h1 style='margin:0'>🌾 AI Agent for Smart Agriculture + Local Nowcast</h1>
        <p style='margin:0'>Get farming advice (AI + weather + soil) and quick local rain nowcasting.</p>
      </div>
    </div>
    <hr/>
""", unsafe_allow_html=True)

# Lottie animation
if hello_animation:
    st_lottie(hello_animation, height=180, key="ai-animation")

# Layout: two main columns
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("1) Location & Weather")
    location = st.text_input("📍 Enter your farm location (village / taluka / district):")

    if location:
        with st.spinner("📡 Fetching location & weather..."):
            lat, lon = get_coordinates(location)
            if not lat:
                st.error("❌ Could not find coordinates. Try a more specific location.")
            else:
                st.success(f"✅ Coordinates: ({lat:.6f}, {lon:.6f})")

                past = get_past_weather(lat, lon)
                future = get_future_weather(lat, lon)
                soil = get_soil_data(lat, lon)

                # build DataFrames (guard against empty dicts)
                df_past = pd.DataFrame(past) if past else pd.DataFrame()
                df_future = pd.DataFrame(future) if future else pd.DataFrame()
                if df_past.shape[0] > 0:
                    df_past["date"] = pd.date_range(end=datetime.today() - timedelta(days=1), periods=len(df_past))
                if df_future.shape[0] > 0:
                    df_future["date"] = pd.date_range(start=datetime.today(), periods=len(df_future))

                # Weather chart
                st.markdown("### 📈 Weather Dashboard (Past & Forecast)")
                fig = go.Figure()
                if not df_past.empty:
                    if "temperature_2m_max" in df_past:
                        fig.add_trace(go.Scatter(x=df_past["date"], y=df_past["temperature_2m_max"],
                                                 mode="lines+markers", name="Past Max Temp"))
                    if "temperature_2m_min" in df_past:
                        fig.add_trace(go.Scatter(x=df_past["date"], y=df_past["temperature_2m_min"],
                                                 mode="lines+markers", name="Past Min Temp"))
                    if "precipitation_sum" in df_past:
                        fig.add_trace(go.Bar(x=df_past["date"], y=df_past["precipitation_sum"],
                                             name="Past Rain", marker_color='rgba(0,100,255,0.4)'))

                if not df_future.empty:
                    if "temperature_2m_max" in df_future:
                        fig.add_trace(go.Scatter(x=df_future["date"], y=df_future["temperature_2m_max"],
                                                 mode="lines+markers", name="Forecast Max Temp", line=dict(dash='dash')))
                    if "temperature_2m_min" in df_future:
                        fig.add_trace(go.Scatter(x=df_future["date"], y=df_future["temperature_2m_min"],
                                                 mode="lines+markers", name="Forecast Min Temp", line=dict(dash='dash')))
                    if "precipitation_sum" in df_future:
                        fig.add_trace(go.Bar(x=df_future["date"], y=df_future["precipitation_sum"],
                                             name="Forecast Rain", marker_color='rgba(0,200,255,0.4)'))

                fig.update_layout(title="🌦️ 10-Day Past & Future Weather Overview",
                                  xaxis_title="Date",
                                  yaxis_title="Temperature (°C) / Rainfall (mm)",
                                  legend_title="Legend",
                                  barmode='overlay',
                                  template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)

                # Soil
                st.markdown("### 🌱 Soil Summary")
                st.write(f"- pH: **{soil['phh2o']}**")
                st.write(f"- Organic Carbon: **{soil['ocd']}**")
                st.write(f"- Sand/Silt/Clay: **{soil['sand']}% / {soil['silt']}% / {soil['clay']}%**")

                # AI Advice
                query = st.text_input("💬 Ask about crop, irrigation, pests, or fertilizer:")
                language = st.radio("🌐 Select your language:", ["English", "Gujarati", "Hindi"], index=0, horizontal=True)

                if query:
                    with st.spinner("🤖 AI is thinking..."):
                        advice = get_advice(location, past, future, soil, query, language)
                        st.markdown("### 💡 AI Agent Suggestion:")
                        st.success(advice)

with right_col:
    st.subheader("2) Local Nowcast (Real-time rain)")

    # Nowcast settings
    cadence_min = st.selectbox("Temporal cadence (min)", [1, 5, 10], index=1)
    history_frames = st.slider("History frames (how many past frames to use)", min_value=6, max_value=24, value=12)
    lead_minutes = st.slider("Forecast lead (minutes)", min_value=15, max_value=120, value=60, step=15)
    use_onnx = False
    if ONNX_AVAILABLE:
        use_onnx = st.checkbox("Use ONNX model (onnxruntime available)", value=False)
    st.markdown("**Model input / grid**: Demo uses a mocked 128×128 grid around the point. Replace with your local grid and real radar fetch code.")

    # ONNX model loader UI
    if use_onnx:
        st.markdown("Upload ONNX model (optional):")
        onnx_file = st.file_uploader("Choose ONNX file", type=["onnx"])
        if onnx_file is not None:
            # save to temp and load
            tmp_path = "onnx_model.onnx"
            with open(tmp_path, "wb") as f:
                f.write(onnx_file.read())
            try:
                sess = load_onnx_model(tmp_path)
                st.success("ONNX model loaded.")
            except Exception as e:
                st.error(f"Failed to load ONNX: {e}")
                sess = None
        else:
            sess = None
    else:
        sess = None

    # Nowcast run button
    if st.button("Run Nowcast"):
        if not location:
            st.warning("Enter a location first in the left panel.")
        else:
            with st.spinner("Running nowcast..."):
                # 1) fetch frames (mocked here)
                frames_arr = fetch_local_radar_frames_mock(lat, lon, frames=history_frames, H=128, W=128)

                # 2) run inference (ONNX if requested & available, else mock)
                leads = max(1, lead_minutes // cadence_min)
                if sess is not None:
                    try:
                        prob_maps = run_onnx_inference(sess, frames_arr)
                        # ensure shape (leads, H, W)
                        if prob_maps.ndim == 3:
                            pass
                        elif prob_maps.ndim == 4 and prob_maps.shape[0] == 1:
                            prob_maps = prob_maps[0]
                    except Exception as e:
                        st.error(f"ONNX inference failed, falling back to mock: {e}")
                        prob_maps = run_model_mock(frames_arr, leads=leads)
                else:
                    prob_maps = run_model_mock(frames_arr, leads=leads)

                # 3) show last frames and nowcast results
                st.markdown("**Recent radar frames (mock)**")
                # show small image grid of last 3 frames
                last3 = frames_arr[-3:]
                cols = st.columns(3)
                for i, c in enumerate(cols):
                    with c:
                        st.image((last3[i]*255).astype('uint8'), caption=f"t-{3-i} frame", clamp=True, use_column_width=True)

                st.markdown("**Nowcast probability maps**")
                # show 3 lead maps (early / mid / last)
                idxs = [0, max(0, leads//2), leads-1]
                for idx in idxs:
                    st.markdown(f"t+{(idx+1)*cadence_min} minutes")
                    # convert to image-like heatmap
                    map_img = (prob_maps[idx] * 255).astype('uint8')
                    st.image(map_img, clamp=True, use_column_width=True)

                # Point forecast at center pixel
                px, py = prob_maps.shape[1]//2, prob_maps.shape[2]//2
                chance_next = float(prob_maps.mean())
                st.metric(label="Chance of precipitation (avg next leads)", value=f"{chance_next*100:.1f}%")
                # Also show per-lead probabilities for center pixel
                lead_probs = {f"t+{(i+1)*cadence_min}m": float(prob_maps[i, px, py]) for i in range(prob_maps.shape[0])}
                st.write("Center-point lead probabilities (sample):")
                # show as small dataframe
                df_leads = pd.DataFrame({
                    "lead_min": [(i+1)*cadence_min for i in range(prob_maps.shape[0])],
                    "prob": [round(float(prob_maps[i, px, py]), 3) for i in range(prob_maps.shape[0])]
                })
                st.dataframe(df_leads)

                st.success("Nowcast complete")
                st.write({
                    "lat": lat, "lon": lon,
                    "chance_next_avg": round(chance_next, 3),
                    "lead_minutes": lead_minutes,
                    "last_input": datetime.utcnow().isoformat() + "Z",
                    "inference_time_s": round(time.time() - time.time(), 2)  # placeholder
                })

# Footer
st.markdown("---")
st.caption("This app demo combines AI advice and a local nowcast demo. Replace mocked radar and mock model with your real radar ingestion and trained model (ONNX/Torch/TF).")

# ----------------- End of file -----------------