import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ----------------- App Setup -----------------
st.set_page_config(page_title="🌦️ Rain & Weather Insights", layout="centered", page_icon="☔")
st.title("☔ Rain Forecast & Weather Insights (India Edition)")
st.markdown("📍 Simple & Local-Friendly Weather App with Rain Analysis")

# ----------------- User Input -----------------
st.sidebar.header("🧭 Settings")
cities = st.sidebar.multiselect("Select Cities to Compare:", ["Ahmedabad", "Surat", "Rajkot", "Vadodara"], default=["Ahmedabad"])
st.sidebar.info("Tip: You can select more than one city to compare rainfall.")
show_past = st.sidebar.checkbox("Show Past 5 Days Data", True)
show_future = st.sidebar.checkbox("Show Future 5 Days Forecast", True)

# ----------------- API Setup -----------------
api_key = st.secrets.get("api_key", "")
if not api_key:
    st.error("⚠️ API key missing! Add your OpenWeatherMap API key in Streamlit → Settings → Secrets.")
    st.info('Example:\n\napi_key = "your_real_api_key_here"')
    st.stop()

# ----------------- Function to Fetch Weather -----------------
def fetch_weather(city):
    try:
        url_forecast = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
        r = requests.get(url_forecast, timeout=10)
        if r.status_code != 200:
            return None, f"City not found: {city}"

        data = r.json()
        lat, lon = data["city"]["coord"]["lat"], data["city"]["coord"]["lon"]

        forecast_list = data.get("list", [])
        df_future = pd.DataFrame([{
            "Datetime": datetime.fromtimestamp(item["dt"]),
            "Rain (mm)": item.get("rain", {}).get("3h", 0.0),
            "Temperature (°C)": item["main"]["temp"],
            "Humidity (%)": item["main"]["humidity"],
            "Wind (km/h)": round(item["wind"]["speed"] * 3.6, 1),
            "Condition": item["weather"][0]["description"].capitalize()
        } for item in forecast_list])
        df_future["Date"] = df_future["Datetime"].dt.date
        df_future = df_future.groupby("Date").agg({
            "Rain (mm)": "sum",
            "Temperature (°C)": "mean",
            "Humidity (%)": "mean",
            "Wind (km/h)": "mean"
        }).reset_index()

        # ---- Past Data ----
        df_past = pd.DataFrame()
        if show_past:
            for i in range(1, 6):
                dt = int((datetime.utcnow() - timedelta(days=i)).timestamp())
                url_past = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={dt}&appid={api_key}&units=metric"
                rp = requests.get(url_past)
                if rp.status_code == 200:
                    past_data = rp.json()
                    rain_total = sum(h.get("rain", {}).get("1h", 0.0) for h in past_data.get("hourly", []))
                    df_past = pd.concat([df_past, pd.DataFrame({
                        "Date": [(datetime.utcnow() - timedelta(days=i)).date()],
                        "Rain (mm)": [round(rain_total, 2)]
                    })])

        # Combine
        df_future["Type"] = "Forecast"
        df_past["Type"] = "Past"
        df = pd.concat([df_past, df_future], ignore_index=True)
        df["City"] = city
        return df, None
    except Exception as e:
        return None, str(e)

# ----------------- Display Results -----------------
all_data = []
for city in cities:
    df, err = fetch_weather(city)
    if err:
        st.warning(err)
    else:
        all_data.append(df)

if all_data:
    df_all = pd.concat(all_data, ignore_index=True)

    # ---- Show Table ----
    st.subheader("📊 Combined Rain Data")
    st.dataframe(df_all, use_container_width=True)

    # ---- Rain Analysis ----
    st.subheader("🧠 Simple Rain Analysis")
    for city in cities:
        city_df = df_all[df_all["City"] == city]
        upcoming_rain = city_df[city_df["Type"] == "Forecast"]["Rain (mm)"].sum()
        if upcoming_rain > 40:
            msg = f"🌧️ **{city}** → Heavy rainfall expected! (ભારે વરસાદની શક્યતા)"
        elif upcoming_rain > 10:
            msg = f"🌦️ **{city}** → Moderate rain expected. (મધ્યમ વરસાદ પડશે)"
        else:
            msg = f"☀️ **{city}** → Mostly dry weather. (વરસાદની શક્યતા ઓછી)"
        st.info(msg)

    # ---- Rain Chart ----
    st.subheader("📈 Rainfall Comparison")
    fig_rain = go.Figure()
    for city in cities:
        city_df = df_all[df_all["City"] == city]
        fig_rain.add_trace(go.Bar(
            x=city_df["Date"], y=city_df["Rain (mm)"], name=city
        ))
    fig_rain.update_layout(
        title="Rainfall Trend (Past + Forecast)",
        xaxis_title="Date", yaxis_title="Rain (mm)",
        barmode="group"
    )
    st.plotly_chart(fig_rain, use_container_width=True)

    # ---- Weather Trends ----
    st.subheader("🌡️ Temperature & Humidity Trend (Forecast Only)")
    fig_weather = go.Figure()
    for city in cities:
        city_df = df_all[(df_all["City"] == city) & (df_all["Type"] == "Forecast")]
        fig_weather.add_trace(go.Scatter(x=city_df["Date"], y=city_df["Temperature (°C)"], name=f"{city} Temp (°C)", mode="lines+markers"))
        fig_weather.add_trace(go.Scatter(x=city_df["Date"], y=city_df["Humidity (%)"], name=f"{city} Humidity (%)", mode="lines+markers"))
    fig_weather.update_layout(title="Temperature & Humidity Trend", xaxis_title="Date")
    st.plotly_chart(fig_weather, use_container_width=True)

    st.success("✅ All weather insights generated successfully!")
else:
    st.warning("Please select at least one valid city.")