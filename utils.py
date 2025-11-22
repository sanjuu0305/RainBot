import requests, pandas as pd, tempfile, os
from datetime import datetime
from deep_translator import GoogleTranslator

# Optional voice libraries
_have_gtts = _have_sr = _have_pydub = False
_gtts_err = _sr_err = _pydub_err = None
try: from gtts import gTTS; _have_gtts=True
except Exception as e: _gtts_err=e
try: import speech_recognition as sr; _have_sr=True
except Exception as e: _sr_err=e
try: from pydub import AudioSegment; _have_pydub=True
except Exception as e: _pydub_err=e

# ---------------- Language translation ----------------
def translate_text(text, language="English"):
    if language=="English": return text
    target = "hi" if language=="Hindi" else "gu"
    try: return GoogleTranslator(source="auto", target=target).translate(text)
    except: return text

# ---------------- Geocoding & Forecast ----------------
def geocode_city(city_name, api_key):
    try:
        r = requests.get("http://api.openweathermap.org/geo/1.0/direct",
                         params={"q":city_name,"limit":1,"appid":api_key}, timeout=10)
        if r.status_code!=200: return None,None,f"Error {r.status_code}"
        data=r.json()
        if not data: return None,None,"No result"
        return data[0]["lat"], data[0]["lon"], None
    except Exception as e: return None,None,f"Geocode error: {e}"

def fetch_forecast(lat, lon, api_key):
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                         params={"lat":lat,"lon":lon,"appid":api_key,"units":"metric"}, timeout=12)
        if r.status_code!=200: return None,f"Error {r.status_code}"
        return r.json(), None
    except Exception as e: return None,f"Forecast error: {e}"

def build_forecast_df(forecast_json):
    items=forecast_json.get("list",[])
    rows=[]
    for it in items:
        dt=datetime.fromtimestamp(it.get("dt",0))
        temp=it.get("main",{}).get("temp")
        hum=it.get("main",{}).get("humidity")
        rain=it.get("rain",{}).get("3h",0.0) if it.get("rain") else 0.0
        cond=it.get("weather",[{}])[0].get("description","").capitalize()
        wind=round(it.get("wind",{}).get("speed",0.0)*3.6,1)
        rows.append({"Datetime":dt,"Date":dt.date(),"Temperature (°C)":temp,
                     "Humidity (%)":hum,"Rain (mm)":rain,"Condition":cond,"Wind (km/h)":wind})
    return pd.DataFrame(rows)

# ---------------- Farmer advisory ----------------
def compose_advice(today_rain, avg_temp, avg_hum, crop=None):
    advice=""
    if today_rain>30: advice="Heavy rain expected — avoid fertilizer, secure crops/livestock, ensure drainage."
    elif today_rain>10: advice="Moderate rain — delay irrigation/spraying; prepare drainage."
    elif today_rain>0: advice="Light rain — minimal irrigation; cover sensitive crops if heavier rain later."
    else: advice="No rain — schedule irrigation/fertilizer on dry day."
    if avg_temp:
        if avg_temp>35: advice+=" High temperatures — apply mulch, irrigate cooler hours."
        elif avg_temp<20: advice+=" Cooler weather — suitable for sowing wheat/mustard."
    if avg_hum and avg_hum>85: advice+=" High humidity — monitor for fungal diseases, use protection."
    if crop:
        if crop.lower()=="rice": advice+=" Rice: prefer level fields; ensure proper drainage."
        elif crop.lower()=="wheat": advice+=" Wheat: sowing ideal in cooler, dry conditions."
        elif crop.lower()=="maize": advice+=" Maize: irrigation needed in early growth stages."
    return advice

# ---------------- TTS & STT ----------------
def text_to_speech(text, lang_code="en"):
    if not _have_gtts: raise RuntimeError(f"gTTS missing: {_gtts_err}")
    tts=gTTS(text=text, lang=lang_code)
    tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3"); tmp_name=tmp.name; tmp.close()
    tts.save(tmp_name); return tmp_name

def transcribe_audio(uploaded_file, language="English"):
    if not _have_sr: return None,f"SpeechRecognition missing: {_sr_err}"
    if not _have_pydub: return None,f"Pydub missing: {_pydub_err}"
    try:
        with tempfile.NamedTemporaryFile(delete=False,suffix=os.path.splitext(uploaded_file.name)[1]) as f:
            f.write(uploaded_file.read()); src_path=f.name
        audio=AudioSegment.from_file(src_path)
        wav_path=src_path+".wav"; audio.export(wav_path,format="wav")
        recognizer=sr.Recognizer()
        with sr.AudioFile(wav_path) as source: audio_data=recognizer.record(source)
        sr_lang={"English":"en-US","Hindi":"hi-IN","Gujarati":"gu-IN"}.get(language,"en-US")
        text=recognizer.recognize_google(audio_data,language=sr_lang)
        return text,None
    except Exception as e: return None,f"Transcription error: {e}"
    finally:
        try: os.remove(src_path); os.remove(wav_path)
        except: pass
