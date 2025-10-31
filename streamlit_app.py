import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ----------------- App Setup -----------------
st.set_page_config(page_title="🌧️ Varsad Forecast", layout="wide", page_icon="☁️")

st.title("☁️ Gujarat Varsad (Rain) Forecast")
st.markdown("આ એપ્લિકેશન તમને તમારા શહેરમાં **પાછલા અને આવતા ૫ દિવસનો વરસાદનો અંદાજ** બતાવે છે 💧")

city = st.text_input("🏙️ શહેરનું નામ લખો:", "Ahmedabad")

# ----------------- API Key -----------------
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error("❌ API key ન મળી. Streamlit Secrets માં ઉમેરો.")
    st.info('Example secrets.toml entry:\n\napi_key = "your_openweathermap_api_key_here"')
    st.stop()

# ----------------- Fetch Data -----------------
if st.button("🔍 વરસાદનો અંદાજ જુઓ"):
    with st.spinner("માહિતી મેળવી રહ્યા છીએ..."):
        try:
            # Current + Forecast Data (Next 5 Days)
            url_forecast = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
            response_forecast = requests.get(url_forecast, timeout=10)
            forecast_data = response_forecast.json()

            # Historical Data (Past 5 Days) using One Call API
            # Step 1: Get City Coordinates
            coord = forecast_data["city"]["coord"]
            lat, lon = coord["lat"], coord["lon"]

            end_time = int(datetime.now().timestamp())
            past_records = []
            for i in range(1, 6):  # past 5 days
                day_time = end_time - i * 86400  # subtract days in seconds
                url_past = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={day_time}&appid={api_key}&units=metric"
                past_res = requests.get(url_past, timeout=10).json()
                for h in past_res.get("hourly", []):
                    past_records.append({
                        "Datetime": datetime.fromtimestamp(h["dt"]),
                        "Rain (mm)": h.get("rain", {}).get("1h", 0.0),
                        "Temperature (°C)": h["temp"],
                        "Humidity (%)": h["humidity"],
                        "Type": "Past"
                    })

            # Forecast (Next 5 Days)
            forecast_list = forecast_data["list"]
            future_records = [{
                "Datetime": datetime.fromtimestamp(item["dt"]),
                "Rain (mm)": item.get("rain", {}).get("3h", 0.0),
                "Temperature (°C)": item["main"]["temp"],
                "Humidity (%)": item["main"]["humidity"],
                "Type": "Forecast"
            } for item in forecast_list]

            # Combine data
            df = pd.DataFrame(past_records + future_records)

            # Daily sum for easier understanding
            df["Date"] = df["Datetime"].dt.date
            daily_data = df.groupby(["Date", "Type"]).agg({
                "Rain (mm)": "sum",
                "Temperature (°C)": "mean",
                "Humidity (%)": "mean"
            }).reset_index()

            # ----------------- Simple Summary -----------------
            st.subheader(f"📍 {city.capitalize()} માટે વરસાદની માહિતી")
            last_past = daily_data[daily_data["Type"] == "Past"].tail(3)
            next_fore = daily_data[daily_data["Type"] == "Forecast"].head(5)

            avg_past = last_past["Rain (mm)"].mean()
            avg_fore = next_fore["Rain (mm)"].mean()

            if avg_fore > avg_past:
                st.success("🌧️ આગામી દિવસોમાં વરસાદ વધવાની શક્યતા છે.")
            else:
                st.info("☀️ હાલ વરસાદ ઓછો દેખાઈ રહ્યો છે અથવા સ્થિર રહેશે.")

            # ----------------- Charts -----------------
            st.subheader("📊 10 દિવસનો વરસાદ ગ્રાફ (પાછલા + આવતા દિવસો)")

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=daily_data[daily_data["Type"] == "Past"]["Date"],
                y=daily_data[daily_data["Type"] == "Past"]["Rain (mm)"],
                name="પાછલો વરસાદ (mm)",
                marker_color="lightblue"
            ))

            fig.add_trace(go.Bar(
                x=daily_data[daily_data["Type"] == "Forecast"]["Date"],
                y=daily_data[daily_data["Type"] == "Forecast"]["Rain (mm)"],
                name="આગામી વરસાદ (mm)",
                marker_color="deepskyblue"
            ))

            fig.update_layout(
                title="☔ છેલ્લા અને આવતા દિવસોનો વરસાદ",
                xaxis_title="તારીખ",
                yaxis_title="વરસાદ (mm)",
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)

            # ----------------- Data Table -----------------
            st.subheader("📋 દિવસ મુજબ વરસાદ, તાપમાન અને ભેજ")
            st.dataframe(daily_data, use_container_width=True)

            # ----------------- Map -----------------
            st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

            st.caption("માહિતી સ્રોત: OpenWeatherMap.org")

        except Exception as e:
            st.error(f"⚠️ Error: {e}")