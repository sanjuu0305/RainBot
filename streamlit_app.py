streamlit_app.py

""" Local AI-based Nowcast Streamlit App (mocked) — Single-file app you can run and deploy to Streamlit Community Cloud via GitHub.

Features added in this update:

Theme toggle (Light / Dark) via simple CSS injection.

Additional weather features: hourly forecast ingestion (Open-Meteo) and a timeline that combines ML nowcast probability with hourly forecast precipitation.

Small UI/UX improvements and extra cached helpers.


NOTE: The app still uses mocked radar and mock model functions. Replace fetch_local_radar_frames_mock() and run_model_mock() with your real radar ingestion and model inference code. """

import streamlit as st import numpy as np import time from datetime import datetime, timedelta import matplotlib.pyplot as plt import base64 import requests import pandas as pd from scipy.ndimage import gaussian_filter import plotly.graph_objects as go

------------------ Page config ------------------

st.set_page_config(page_title="Local Rain Nowcast", layout="wide")

------------------ Theme CSS ------------------

LIGHT_CSS = """ body { background-color: white; color: #111; } """ DARK_CSS = """ body { background-color: #0e1117; color: #e6eef8; } .stMarkdown, .stText, .stButton { color: #e6eef8; } """

def apply_theme(theme: str): css = DARK_CSS if theme == "Dark" else LIGHT_CSS st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

------------------ App header ------------------

st.title("Local-area AI Rain Nowcast (Demo)") st.markdown("Quick demo Streamlit app for local nowcasting. Replace mocked data/model with real code.")

------------------ Sidebar settings ------------------

st.sidebar.header("Nowcast settings") theme = st.sidebar.selectbox("Theme", ["Light", "Dark"], index=0) apply_theme(theme)

lat = st.sidebar.number_input("Latitude", value=23.0225, format="%.6f") lon = st.sidebar.number_input("Longitude", value=72.5714, format="%.6f") resolution_km = st.sidebar.selectbox("Grid resolution (km)", [0.5, 1.0, 2.0], index=1) cadence_min = st.sidebar.selectbox("Temporal cadence (min)", [1, 5, 10], index=1) frames = st.sidebar.slider("Input frames (history)", min_value=6, max_value=24, value=12) lead_minutes = st.sidebar.slider("Forecast lead (minutes)", min_value=15, max_value=120, value=60, step=15) run_button = st.sidebar.button("Run nowcast")

st.sidebar.markdown("---") st.sidebar.markdown("Deployment: Push this repo to GitHub and connect to Streamlit Community Cloud. See README in repo.")

------------------ Weather helpers ------------------

@st.cache_data(ttl=300) def get_hourly_forecast(lat, lon, hours=48): """Fetch hourly forecast (precipitation) for the next hours hours using Open-Meteo.""" try: end = (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:00:00Z") url = ( f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}" f"&hourly=precipitation,temperature_2m,relativehumidity_2m&windspeed_unit=kmh&timezone=UTC" ) r = requests.get(url, timeout=10) if r.status_code != 200: return pd.DataFrame() data = r.json().get("hourly", {}) if not data: return pd.DataFrame() df = pd.DataFrame(data) df["time"] = pd.to_datetime(df["time"])  # UTC times df = df.set_index("time") return df except Exception: return pd.DataFrame()

------------------ Mocked radar/model functions (fixes applied) ------------------

@st.cache_data(ttl=30) def fetch_local_radar_frames_mock(lat, lon, frames=12, H=128, W=128): """Return mocked radar frames as (frames, H, W) numpy array with values 0..1. Replace with real fetch from your local radar tiles, reprojected to local grid.""" rng = np.random.default_rng(seed=abs(int((lat+lon)1e4)) % 2**31) base = rng.random((frames, H, W)) * 0.2 # add a synthetic moving blob to simulate a rain cell for t in range(frames): cx = int(H0.3 + t0.5) cy = int(W0.4 + t0.7) rr = 12 Y, X = np.ogrid[:H, :W] mask = ((X-cx)**2 + (Y-cy)**2) <= rrrr base[t][mask] += 0.7 * np.exp(-t/frames) return np.clip(base, 0.0, 1.0).astype('float32')

@st.cache_resource def load_mock_model(): """Return a placeholder 'model' object. Replace by loading your real model (torch/onnx/tf).""" return {"name": "mock-model"}

def gaussian_blur(img, sigma=1.0): return gaussian_filter(img, sigma=sigma)

def run_model_mock(model, frames_array, leads=12): """Mock inference: advect and blur frames to create probability maps of shape (leads, H, W). Replace with actual model inference that outputs probabilistic precipitation maps.""" frames, H, W = frames_array.shape out = np.zeros((leads, H, W), dtype='float32') last = frames_array[-1] for i in range(leads): shift = i * 2  # advect out[i] = np.roll(last, shift=shift, axis=1) out[i] = gaussian_blur(out[i], sigma=1 + i*0.2) out = np.clip(out, 0.0, 1.0) return out

------------------ Small helpers ------------------

def plot_heatmap(prob_map, title="Prob. (0..1)"): fig, ax = plt.subplots(figsize=(5,5)) im = ax.imshow(prob_map, vmin=0, vmax=1, origin='lower') ax.set_axis_off() ax.set_title(title) cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04) return fig

------------------ Main UI ------------------

col1, col2 = st.columns([1,1])

with col1: st.subheader("Input (recent radar frames)") st.write(f"Location: {lat:.4f}, {lon:.4f} — grid {resolution_km} km — cadence {cadence_min} min — history {frames} frames") frames_arr = fetch_local_radar_frames_mock(lat, lon, frames=frames, H=128, W=128) # show last 3 frames last3 = frames_arr[-3:] fig, axs = plt.subplots(1,3, figsize=(12,4)) for i in range(3): axs[i].imshow(last3[i], origin='lower', vmin=0, vmax=1) axs[i].set_title(f"t-{3-i} frame") axs[i].axis('off') st.pyplot(fig)

with col2: st.subheader("Nowcast output") model = load_mock_model() if run_button: t0 = time.time() leads = max(1, lead_minutes // cadence_min) prob_maps = run_model_mock(model, frames_arr, leads=leads) # pick center pixel as point forecast px, py = prob_maps.shape[1]//2, prob_maps.shape[2]//2 chance_next = float(prob_maps.mean()) st.metric(label="Chance of precipitation (avg next leads)", value=f"{chance_next*100:.1f}%") # show lead panels lead_idx = [0, max(0, leads//3), leads-1] tabs = st.tabs([f"t+{(i+1)*cadence_min}m" for i in lead_idx]) for tab, idx in zip(tabs, lead_idx): with tab: fig_map = plot_heatmap(prob_maps[idx], title=f"Prob t+{(idx+1)*cadence_min}m") st.pyplot(fig_map)

# ----- NEW: combine with hourly forecast -----
    df_hourly = get_hourly_forecast(lat, lon, hours=max(48, lead_minutes//60*24))
    if not df_hourly.empty:
        # extract forecast precipitation for the next `lead_minutes` window
        now_utc = pd.Timestamp.utcnow().floor(f"{cadence_min}min")
        end_time = now_utc + pd.Timedelta(minutes=lead_minutes)
        df_slice = df_hourly.loc[now_utc:end_time]
        precip_forecast_mm = df_slice.get("precipitation", pd.Series(dtype=float))

        # prepare combined timeline: convert prob_maps leads to approximate times
        lead_times = [now_utc + pd.Timedelta(minutes=(i+1)*cadence_min) for i in range(prob_maps.shape[0])]
        lead_probs = [float(prob_maps[i, px, py]) for i in range(prob_maps.shape[0])]

        timeline_df = pd.DataFrame({"time": lead_times, "nowcast_prob": lead_probs})
        # merge with hourly precip (resample hourly precip to minutes if needed)
        # for plotting, we will show nowcast probability (0..1) and forecast precip (mm)

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=precip_forecast_mm.index, y=precip_forecast_mm.values,
                              name="Forecast precip (mm)", yaxis="y2", marker_color='rgba(0,150,255,0.5)'))
        fig2.add_trace(go.Scatter(x=timeline_df["time"], y=timeline_df["nowcast_prob"],
                                  mode="lines+markers", name="Nowcast P(rain)", yaxis="y1", line=dict(width=2)))
        fig2.update_layout(
            title="Nowcast probability vs Hourly forecast precipitation",
            xaxis_title="Time (UTC)",
            yaxis=dict(title="Nowcast probability", range=[0,1]),
            yaxis2=dict(title="Precipitation (mm)", overlaying="y", side="right"),
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Hourly forecast not available — make sure Open-Meteo is reachable.")

    st.write("

") st.write({ "lat": lat, "lon": lon, "chance_next_avg": round(chance_next, 3), "lead_minutes": lead_minutes, "last_input": datetime.utcnow().isoformat() + "Z", "inference_time_s": round(time.time() - t0, 2) }) else: st.info("Adjust settings in the sidebar and click Run nowcast to generate a demo prediction.")

st.markdown('---') st.caption('This demo uses mocked radar + model. Replace fetch_local_radar_frames_mock and run_model_mock with real code and load your trained model (preferably as ONNX or a small TF/Torch model for inference).')

------------------ Footer / download demo artifacts ------------------

st.markdown("### Helpful files & deploy notes") st.markdown("- requirements.txt and a short README.md are provided in the repository. Push to GitHub and connect to Streamlit Community Cloud for automatic deploy.")

------------------ End of streamlit_app.py ------------------
