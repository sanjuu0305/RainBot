import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ----------------- App Setup -----------------
st.set_page_config(page_title="🌦️ Easy Rain Forecast", layout="centered", page_icon="☔")

st.title("☔ Simple Rain Forecast & Analysis")
st.markdown("**Get Past & Future 5-Day Rain Data — Simple View for Local Users**")

city = st.text_input("🏙️ Enter your City Name:", "Ahmedabad")

# ----------------- API Setup -----------------
api_key = st.secrets.get("api_key", "")
if not api_key:
    st.error("⚠️ API key missing! Add your OpenWeatherMap API key in Streamlit → Settings → Secrets.")
    st.info('Example:\n\napi_key = "your_real_api_key_here"')
    st.stop()

# ----------------- Fetch Weather Data -----------------
if st.button("🔍 Show Rain Forecast"):
    with st.spinner("Fetching weather data..."):
        # Forecast (next 5 days)
        url_future = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
        # Past 5 days (using One Call API Timemachine)
        try:
            forecast_response = requests.get(url_future, timeout=10)
            forecast_data = forecast_response.json()

            if forecast_response.status_code != 200:
                st.error(f"API Error: {forecast_data.get('message', 'Invalid City Name')}")
                st.stop()

            city_info = forecast_data.get("city", {})
            lat = city_info.get("coord", {}).get("lat")
            lon = city_info.get("coord", {}).get("lon")

            if not lat or not lon:
                st.error("City coordinates not found.")
                st.stop()

            # ---- Past Data (last 5 days) ----
            past_days = []
            for i in range(1, 6):
                dt = int((datetime.utcnow() - timedelta(days=i)).timestamp())
                url_past = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={dt}&appid={api_key}&units=metric"
                r = requests.get(url_past)
                if r.status_code == 200:
                    past_data = r.json()
                    rain_total = sum(h.get("rain", {}).get("1h", 0.0) for h in past_data.get("hourly", []))
                    past_days.append({
                        "Date": (datetime.utcnow() - timedelta(days=i)).date(),
                        "Rain (mm)": round(rain_total, 2)
                    })

            past_df = pd.DataFrame(past_days)
            past_df = past_df.sort_values("Date")

            # ---- Future Data (next 5 days) ----
            forecast_list = forecast_data.get("list", [])
            future_df = pd.DataFrame([{
                "Datetime": datetime.fromtimestamp(item["dt"]),
                "Rain (mm)": item.get("rain", {}).get("3h", 0.0)
            } for item in forecast_list])

            future_daily = future_df.groupby(future_df["Datetime"].dt.date)["Rain (mm)"].sum().reset_index()
            future_daily.columns = ["Date", "Rain (mm)"]

            # ---- Combine Past + Future ----
            full_df = pd.concat([past_df, future_daily], ignore_index=True)
            full_df["Type"] = ["Past"] * len(past_df) + ["Forecast"] * len(future_daily)

            # ---- Display Table ----
            st.subheader(f"📊 Rain Data for {city.capitalize()}")
            st.dataframe(full_df, use_container_width=True)

            # ---- Simple Rain Analysis ----
            avg_rain = full_df["Rain (mm)"].mean()
            total_future_rain = future_daily["Rain (mm)"].sum()

            if total_future_rain > 40:
                rain_msg = "🌧️ **Heavy rainfall likely!** Keep umbrella ready. (ભારે વરસાદની શક્યતા)"
            elif total_future_rain > 10:
                rain_msg = "🌦️ **Moderate rainfall expected.** (મધ્યમ વરસાદ પડશે)"
            else:
                rain_msg = "☀️ **Mostly dry weather.** (મોટાભાગે વરસાદ નહીં પડે)"

            st.info(rain_msg)

            # ---- Visualization ----
            st.subheader("📈 Past & Future Rainfall Trend")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=full_df["Date"],
                y=full_df["Rain (mm)"],
                marker_color=["#90CAF9" if t == "Past" else "#1E88E5" for t in full_df["Type"]],
                name="Rain (mm)"
            ))
            fig.update_layout(
                title="Rainfall (Past & Next 5 Days)",
                xaxis_title="Date",
                yaxis_title="Rain (mm)"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.success("✅ Rain forecast loaded successfully!")

        except Exception as e:
            st.error(f"Error: {e}")