import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
import holidays
import requests
import pytz
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Gwalior Traffic Forecaster", page_icon="🚗", layout="wide")

# --- CONFIGURATION & MODEL LOADING ---
MODEL_PATH = "models/traffic_model.joblib"
GWALIOR_LAT = 26.2183
GWALIOR_LON = 78.1828
IST = pytz.timezone('Asia/Kolkata')
indian_holidays = holidays.India(state='MP', years=datetime.now().year)

MODEL_COLUMNS = [
    'base_travel_time_seconds', 'day_of_week', 'hour_of_day',
    'is_market_closed', 'is_holiday', 'weather',
    'route_name_CityCenter-to-Palace', 'route_name_Fort-to-Station',
    'route_name_Highway-Bypass', 'route_name_Mall-to-IIITM',
    'route_name_Thatipur-to-Morar'
]

@st.cache_resource
def load_model(path):
    return joblib.load(path)

model = load_model(MODEL_PATH)

# --- LIVE DATA FUNCTIONS ---

@st.cache_data(ttl=600)
def get_live_weather(api_key, lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
    try:
        response = requests.get(url)
        data = response.json()
        weather_main = data['weather'][0]['main']
        if 'Rain' in weather_main or 'Drizzle' in weather_main or 'Thunderstorm' in weather_main:
            return 2, f"Rainy 🌧️ ({weather_main})"
        elif 'Clouds' in weather_main:
            return 1, f"Cloudy ☁️ ({weather_main})"
        else:
            return 0, f"Clear ☀️ ({weather_main})"
    except Exception:
        return 0, "Clear ☀️ (default)"

@st.cache_data(ttl=3600)
def get_coordinates(api_key, location_name):
    url = f"https://api.tomtom.com/search/2/geocode/{location_name}, Gwalior, India.json?key={api_key}&lat={GWALIOR_LAT}&lon={GWALIOR_LON}"
    try:
        response = requests.get(url)
        data = response.json()
        if data and data['results']:
            pos = data['results'][0]['position']
            return f"{pos['lat']},{pos['lon']}"
    except Exception:
        return None
    return None

@st.cache_data(ttl=600)
def get_route_details(api_key, start_coords, end_coords):
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{start_coords}:{end_coords}/json?key={api_key}&travelMode=car&traffic=false&routeType=fastest"
    try:
        response = requests.get(url)
        data = response.json()
        if 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            base_time = route['summary']['travelTimeInSeconds']
            points = route['legs'][0]['points']
            route_geometry = [[p['latitude'], p['longitude']] for p in points]
            return base_time, route_geometry
    except Exception:
        return None, None
    return None, None

# --- STREAMLIT APP INTERFACE ---

st.title("🚗 Gwalior Smart Traffic Forecaster")
st.write("Enter any start and end location within Gwalior to get a real-time traffic forecast.")

# FIX 1: Initialize session state
if 'prediction_made' not in st.session_state:
    st.session_state.prediction_made = False
    st.session_state.results = {}

WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", "")
TOMTOM_API_KEY = st.secrets.get("TOMTOM_API_KEY", "")

if not WEATHER_API_KEY or not TOMTOM_API_KEY:
    st.warning("API Keys not configured. Please contact the app owner.")

col1, col2 = st.columns(2)
with col1:
    origin = st.text_input("📍 Where are you starting from?", "Kailash Nagar")
with col2:
    destination = st.text_input("🏁 Where are you going?", "Gwalior Railway Station")

if st.button("Predict Travel Time", disabled=(not WEATHER_API_KEY or not TOMTOM_API_KEY), use_container_width=True):
    with st.spinner("Analyzing routes and live conditions..."):
        start_coords = get_coordinates(TOMTOM_API_KEY, origin)
        end_coords = get_coordinates(TOMTOM_API_KEY, destination)

        if not start_coords or not end_coords:
            st.error("Could not find one or both locations. Please be more specific (e.g., add 'Gwalior').")
            st.session_state.prediction_made = False
        else:
            base_time, route_geometry = get_route_details(TOMTOM_API_KEY, start_coords, end_coords)
            if not base_time or base_time > 10800:
                st.error("Could not calculate a reasonable route. Please check the locations.")
                st.session_state.prediction_made = False
            else:
                now_ist = datetime.now(IST)
                # ... (rest of the prediction logic)
                prediction_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
                prediction_df['base_travel_time_seconds'] = base_time
                prediction_df['day_of_week'] = now_ist.weekday()
                prediction_df['hour_of_day'] = now_ist.hour
                prediction_df['is_market_closed'] = 1 if now_ist.weekday() == 1 else 0
                prediction_df['is_holiday'] = 1 if now_ist.date() in indian_holidays else 0
                weather_code, weather_desc = get_live_weather(WEATHER_API_KEY, GWALIOR_LAT, GWALIOR_LON)
                prediction_df['weather'] = weather_code
                prediction_df['route_name_Thatipur-to-Morar'] = 1

                predicted_seconds = model.predict(prediction_df)
                predicted_minutes = predicted_seconds[0] / 60
                
                # FIX 2: Save results to session state instead of displaying them
                st.session_state.prediction_made = True
                st.session_state.results = {
                    "predicted_minutes": predicted_minutes,
                    "now_ist": now_ist,
                    "weather_desc": weather_desc,
                    "route_geometry": route_geometry,
                    "start_coords": start_coords,
                    "end_coords": end_coords,
                    "origin": origin,
                    "destination": destination
                }

# FIX 3: Display results outside the button 'if' block, based on session state
if st.session_state.prediction_made and st.session_state.results:
    results = st.session_state.results
    st.success(f"**Estimated Travel Time: {results['predicted_minutes']:.2f} minutes**")
    st.info(f"**Live Conditions:** {results['now_ist'].strftime('%I:%M %p')}, {results['now_ist'].strftime('%A')}, {results['weather_desc']}")
    
    if results['route_geometry']:
        st.subheader("Recommended Route")
        map_center = [GWALIOR_LAT, GWALIOR_LON]
        m = folium.Map(location=map_center, zoom_start=12)
        folium.PolyLine(results['route_geometry'], color="blue", weight=5, opacity=0.8).add_to(m)
        
        start_lat, start_lon = map(float, results['start_coords'].split(','))
        end_lat, end_lon = map(float, results['end_coords'].split(','))
        folium.Marker([start_lat, start_lon], popup=f"Start: {results['origin']}", icon=folium.Icon(color='green')).add_to(m)
        folium.Marker([end_lat, end_lon], popup=f"End: {results['destination']}", icon=folium.Icon(color='red')).add_to(m)

        st_folium(m, width="100%", height=500, returned_objects=[])
