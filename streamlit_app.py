streamlit_app.py

""" Local AI-based Nowcast Streamlit App (mocked) — Single-file app you can run and deploy to Streamlit Community Cloud via GitHub.

Files included in this document (create these in your repo):

streamlit_app.py            (this file)

requirements.txt           (below)

README.md                  (deploy instructions below)


NOTE: The app contains mocked data-fetch and model-run functions. Replace fetch_local_radar_frames() and run_model() with real implementations that load local radar tiles and your trained model (ONNX / Torch / TF). """

import streamlit as st import numpy as np import time from datetime import datetime import matplotlib.pyplot as plt from matplotlib.colors import ListedColormap import base64

st.set_page_config(page_title="Local Rain Nowcast", layout="wide")

------------------ App header ------------------

st.title("Local-area AI Rain Nowcast (Demo)") st.markdown("Quick demo Streamlit app for local nowcasting. Replace mocked data/model with real code.")

------------------ Sidebar settings ------------------

st.sidebar.header("Nowcast settings") lat = st.sidebar.number_input("Latitude", value=23.0225, format="%.6f") lon = st.sidebar.number_input("Longitude", value=72.5714, format="%.6f") resolution_km = st.sidebar.selectbox("Grid resolution (km)", [0.5, 1.0, 2.0], index=1) cadence_min = st.sidebar.selectbox("Temporal cadence (min)", [1, 5, 10], index=1) frames = st.sidebar.slider("Input frames (history)", min_value=6, max_value=24, value=12) lead_minutes = st.sidebar.slider("Forecast lead (minutes)", min_value=15, max_value=120, value=60, step=15) run_button = st.sidebar.button("Run nowcast")

st.sidebar.markdown("---") st.sidebar.markdown("Deployment: Push this repo to GitHub and connect to Streamlit Community Cloud. See README in repo.")

------------------ Mocked data/model functions ------------------

@st.cache_data(ttl=30) def fetch_local_radar_frames_mock(lat, lon, frames=12, H=128, W=128): """Return mocked radar frames as (frames, H, W) numpy array with values 0..1. Replace with real fetch from your local radar tiles, reprojected to local grid.""" rng = np.random.default_rng(seed=int((lat+lon)1e4) % 2**31) base = rng.random((frames, H, W)) * 0.2 n    # add a synthetic moving blob to simulate a rain cell for t in range(frames): cx = int(H0.3 + t0.5) cy = int(W0.4 + t0.7) rr = 12 Y, X = np.ogrid[:H, :W] mask = ((X-cx)**2 + (Y-cy)**2) <= rrrr base[t][mask] += 0.7 * np.exp(-t/frames) return np.clip(base, 0.0, 1.0).astype('float32')

@st.cache_resource def load_mock_model(): """Return a placeholder 'model' object. Replace by loading your real model (torch/onnx/tf).""" return {"name": "mock-model"}

def run_model_mock(model, frames_array, leads=12): """Mock inference: advect and blur frames to create probability maps of shape (leads, H, W). Replace with actual model inference that outputs probabilistic precipitation maps.""" frames, H, W = frames_array.shape out = np.zeros((leads, H, W), dtype='float32') last = frames_array[-1] for i in range(leads): shift = i * 2  # advect out[i] = np.roll(last, shift=shift, axis=1) out[i] = gaussian_blur(out[i], sigma=1 + i*0.2) out = np.clip(out, 0.0, 1.0) return out

------------------ Small helpers ------------------

from scipy.ndimage import gaussian_filter

def gaussian_blur(img, sigma=1.0): return gaussian_filter(img, sigma=sigma)

def plot_heatmap(prob_map, title="Prob. (0..1)"): fig, ax = plt.subplots(figsize=(5,5)) cmap = plt.cm.get_cmap('Blues') im = ax.imshow(prob_map, vmin=0, vmax=1, origin='lower') ax.set_axis_off() ax.set_title(title) cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04) return fig

------------------ Main UI ------------------

col1, col2 = st.columns([1,1])

with col1: st.subheader("Input (recent radar frames)") st.write(f"Location: {lat:.4f}, {lon:.4f} — grid {resolution_km} km — cadence {cadence_min} min — history {frames} frames") frames_arr = fetch_local_radar_frames_mock(lat, lon, frames=frames, H=128, W=128) # show last 3 frames last3 = frames_arr[-3:] fig, axs = plt.subplots(1,3, figsize=(12,4)) for i in range(3): axs[i].imshow(last3[i], origin='lower', vmin=0, vmax=1) axs[i].set_title(f"t-{3-i} frame") axs[i].axis('off') st.pyplot(fig)

with col2: st.subheader("Nowcast output") model = load_mock_model() if run_button: t0 = time.time() leads = max(1, lead_minutes // cadence_min) prob_maps = run_model_mock(model, frames_arr, leads=leads) # pick center pixel as point forecast px, py = prob_maps.shape[1]//2, prob_maps.shape[2]//2 chance_next = float(prob_maps.mean()) st.metric(label="Chance of precipitation (avg next leads)", value=f"{chance_next*100:.1f}%") # show lead panels lead_idx = [0, max(0, leads//3), leads-1] tabs = st.tabs([f"t+{(i+1)*cadence_min}m" for i in lead_idx]) for tab, idx in zip(tabs, lead_idx): with tab: fig_map = plot_heatmap(prob_maps[idx], title=f"Prob t+{(idx+1)*cadence_min}m") st.pyplot(fig_map) st.write("\n") st.write({ "lat": lat, "lon": lon, "chance_next_avg": round(chance_next, 3), "lead_minutes": lead_minutes, "last_input": datetime.utcnow().isoformat() + "Z", "inference_time_s": round(time.time() - t0, 2) }) else: st.info("Adjust settings in the sidebar and click Run nowcast to generate a demo prediction.")

st.markdown('---') st.caption('This demo uses mocked radar + model. Replace fetch_local_radar_frames_mock and run_model_mock with real code and load your trained model (preferably as ONNX or a small TF/Torch model for inference).')

------------------ Footer / download demo artifacts ------------------

st.markdown("### Helpful files & deploy notes") st.markdown("- requirements.txt and a short README.md are provided in the repository. Push to GitHub and connect to Streamlit Community Cloud for automatic deploy.")

------------------ End of streamlit_app.py ------------------