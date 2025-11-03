# streamlit_app.py
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

st.set_page_config(page_title="Rain Forecast for Farmers", layout="wide")

# ---------- Translation helper (safe, local) ----------
def translate_text(text: str, language: str) -> str:
    """Lightweight translation mapping for app strings.
       Expand this dict for more keys as needed.
    """
    gu_map = {
        "Choose language / ભાષા પસંદ કરો": "ભાષા પસંદ કરો",
        "Daily Rain Summary (available forecast days)": "દૈનિક વરસાદ સારાંશ (મોજૂદ અનુમાન દિવસો)",
        "Farmer Advisory": "કિસાન સલાહ",
        "Crop Suggestion (based on temperature & rain)": "ફસલ સૂચન (તાપમાન અને વરસાદ પર આધારિત)",
        "Flood Risk Index (simple heuristic)": "બવંડર જોખમ સૂચકાંક (સરળ હ્યોરિસ્ટિક)",
        "LOW — No flood risk": "નીચો — કોઈ પૂર જોખમ નથી",
        "Upload CSV file with forecast data": "અનુમાન ડેટા સાથે CSV અપલોડ કરો",
        "Date": "તારીખ",
        "Rain (mm)": "વર્ષા (મિમી)",
        "Temperature (°C)": "તાપમાન (°C)",
        "Humidity (%)": "આર્દ્રતા (%)",
        "Radar / Layers": "રેડાર / સ્તરો",
        "Language": "ભાષા",
        "No data available. Upload a CSV or provide data.": "કોઇ ડેટા ઉપલબ્ધ નથી. કૃપા કરીને CSV અપલોડ કરો."
    }
    if language == "ગુજરાતી":
        return gu_map.get(text, text)
    return text

# ---------- Sidebar / Language & CSV upload ----------
st.sidebar.header(translate_text("Choose language / ભાષા પસંદ કરો", "English"))
language = st.sidebar.selectbox(translate_text("Language", "English"), ["English", "ગુજરાતી"])

st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader(translate_text("Upload CSV file with forecast data", language),
                                         type=["csv", "xlsx"])

# ---------- Data loader ----------
@st.cache_data
def load_df_from_file(uploaded):
    if uploaded is None:
        return None
    try:
        if str(uploaded.name).lower().endswith(".xlsx"):
            df = pd.read_excel(uploaded)
        else:
            df = pd.read_csv(uploaded)
    except Exception:
        # try different separators if CSV fails
        uploaded.seek(0)
        df = pd.read_csv(uploaded, sep=None, engine="python")
    # Normalize column names (strip)
    df.columns = [c.strip() for c in df.columns]
    # Try parse date
    if "Date" not in df.columns and "date" in [c.lower() for c in df.columns]:
        # map lower-case to actual
        for c in df.columns:
            if c.lower() == "date":
                df.rename(columns={c: "Date"}, inplace=True)
                break
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    # Ensure numeric columns exist
    for col in ["Rain (mm)", "Temperature (°C)", "Humidity (%)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

df = load_df_from_file(uploaded_file)

# If no file, show sample data area or prompt (you can connect API here)
if df is None:
    st.sidebar.info(translate_text("No data available. Upload a CSV or provide data.", language))
    st.header("🌧️ " + translate_text("Daily Rain Summary (available forecast days)", language))
    st.write(translate_text("No data available. Upload a CSV or provide data.", language))
    st.stop()

# ---------- Basic checks ----------
required_cols = ["Date", "Rain (mm)", "Temperature (°C)"]
if not all(col in df.columns for col in required_cols):
    st.error("Missing required columns. Please ensure CSV contains: " + ", ".join(required_cols))
    st.write("Found columns:", df.columns.tolist())
    st.stop()

# Sort by date
df = df.sort_values("Date").reset_index(drop=True)

# ---------- Charts ----------
st.title("🌦️ " + translate_text("Hourly Rain & Temperature", language) if False else "🌦️ Rain & Temperature")
# Top row: line chart for Temperature and bar for Rain (combined)
left_col, right_col = st.columns([3, 1])

with left_col:
    st.subheader(translate_text("Hourly Rain & Temperature", language))
    base = alt.Chart(df).encode(x=alt.X('Date:T', title='Time'))
    rain_bar = base.mark_bar(opacity=0.6).encode(
        y=alt.Y('Rain (mm):Q', title=translate_text("Rain (mm)", language))
    )
    temp_line = base.mark_line(point=True).encode(
        y=alt.Y('Temperature (°C):Q', title=translate_text("Temperature (°C)", language)),
        color=alt.value("#1f77b4")
    ).transform_calculate(_temp='datum["Temperature (°C)"]')
    # Layered chart using two axes is tricky in pure Altair without transform; show 2 charts stacked
    st.altair_chart((rain_bar & temp_line).resolve_scale(y='independent'), use_container_width=True)

with right_col:
    st.subheader(translate_text("Daily Rain Summary (available forecast days)", language))
    st.dataframe(df[[c for c in ["Date", "Rain (mm)", "Temperature (°C)", "Humidity (%)"] if c in df.columns]].head(15))

# ---------- Daily rainfall trend (small) ----------
st.markdown("### " + translate_text("Daily Rainfall Trend", language))
rain_chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X('Date:T', title=translate_text("Date", language)),
    y=alt.Y('Rain (mm):Q', title=translate_text("Rain (mm)", language))
)
st.altair_chart(rain_chart, use_container_width=True)

# ---------- Flood Risk (dynamic) ----------
st.subheader("💧 " + translate_text("Flood Risk Index (simple heuristic)", language))
try:
    # Use sum of next N days for heuristic
    next_days = 3
    # Filter only future dates or include all if forecast only
    today = pd.to_datetime(datetime.utcnow().date())
    upcoming = df[df["Date"] >= today].head(next_days)
    # fallback to first next_days rows if upcoming is empty
    if upcoming.empty:
        upcoming = df.head(next_days)
    total_rain = upcoming["Rain (mm)"].sum(skipna=True)

    if pd.isna(total_rain):
        raise ValueError("Rain data missing")

    if total_rain > 50:
        risk = "🚨 HIGH — Flood risk likely"
        st.error(risk)
    elif total_rain > 20:
        risk = "⚠️ MEDIUM — Watch for flooding"
        st.warning(risk)
    else:
        risk = translate_text("LOW — No flood risk", language)
        st.success(risk)
except Exception as e:
    st.error("Flood risk could not be computed. " + str(e))

# ---------- Farmer Advisory ----------
st.markdown("### " + translate_text("Farmer Advisory", language))
try:
    # use next 3 days for decision
    upcoming = df.head(3)
    rain_next_3_days = upcoming["Rain (mm)"].sum(skipna=True)
    avg_temp = df["Temperature (°C)"].mean(skipna=True)

    if pd.isna(rain_next_3_days) or pd.isna(avg_temp):
        st.info(translate_text("No data available. Upload a CSV or provide data.", language))
    else:
        if rain_next_3_days > 20:
            st.success("🌧️ Heavy rain expected! Delay irrigation or pesticide spraying. Secure storage and livestock.")
        elif rain_next_3_days > 5:
            st.info("☁️ Moderate rain expected. Prepare drainage and avoid heavy field work.")
        elif rain_next_3_days > 0:
            st.info("☁️ Light rain expected. Consider light covering for sensitive produce.")
        else:
            st.warning("☀️ No rain expected. Plan irrigation accordingly; conserve water where possible.")
except Exception as e:
    st.error("Advisory could not be generated: " + str(e))

# ---------- Crop Suggestion ----------
st.markdown("### " + translate_text("Crop Suggestion (based on temperature & rain)", language))
try:
    if pd.isna(avg_temp):
        st.info("Temperature data missing; cannot suggest crops.")
    else:
        if avg_temp < 20:
            st.info("Good time for: wheat, mustard, chickpea.")
        elif 20 <= avg_temp <= 30:
            st.info("Good time for: cotton, paddy, maize.")
        else:
            st.info("High temperature — focus on irrigation-friendly or heat-tolerant crops; monitor moisture.")
except Exception as e:
    st.error("Crop suggestion error: " + str(e))

# ---------- Radar / Layers section (safe translation) ----------
try:
    st.subheader(translate_text("Radar / Layers", language))
    st.write("(If you have radar tile URLs or WMS, you can embed maps here.)")
except Exception as e:
    # safe fallback — this prevents previous TypeError crash
    st.subheader("Radar / Layers")
    st.warning(translate_text("Language translation unavailable", language) if language != "English" else "Language translation unavailable")

# ---------- Footer / tips ----------
st.markdown("---")
st.write("Tips:")
st.write("- Upload a CSV with Date, Rain (mm), Temperature (°C), Humidity (%) columns.")
st.write("- For best results, include forecast rows (future dates).")
st.write("- You can expand translate_text map with more keys or connect to a translation API (handle errors carefully).")