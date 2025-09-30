import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
import holidays
import requests
import pytz
import folium
from streamlit_folium import st_folium
from urllib.parse import quote

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

# --- LIVE DATA FUNCTIONS (UPGRADED) ---

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
def get_coordinates(api_key, location_name, pincode=None):
    # FIX: Add pincode to the query if provided, for better accuracy
    search_query = f"{location_name}, Gwalior, India"
    if pincode and len(pincode) == 6 and pincode.isdigit():
        search_query = f"{location_name}, {pincode}, Gwalior, India"
        
    encoded_location = quote(search_query)
    url = f"https://api.tomtom.com/search/2/geocode/{encoded_location}.json?key={api_key}&lat={GWALIOR_LAT}&lon={GWALIOR_LON}"
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
def get_route_details(api_key, start_coords, end_coords, mode='car'):
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{start_coords}:{end_coords}/json?key={api_key}&travelMode={mode}&traffic=true&routeType=fastest&routeRepresentation=polyline"
    try:
        response = requests.get(url)
        data = response.json()
        if 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            travel_time = route['summary']['trafficTravelTimeInSeconds'] if mode != 'car' else route['summary']['travelTimeInSeconds']
            points = route['legs'][0]['points']
            route_geometry = [[p['latitude'], p['longitude']] for p in points]
            return travel_time, route_geometry
    except Exception:
        return None, None
    return None, None

# --- STREAMLIT APP INTERFACE ---

st.title("🚗 Gwalior Smart Traffic Forecaster")
st.write("Enter any start and end location in Gwalior to get a traffic forecast for different travel modes.")

WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", "")
TOMTOM_API_KEY = st.secrets.get("TOMTOM_API_KEY", "")

if not WEATHER_API_KEY or not TOMTOM_API_KEY:
    st.warning("API Keys not configured. Please contact the app owner.")

# FIX: Add optional pincode fields for better accuracy
st.subheader("📍 Start Location")
col1, col2 = st.columns([3, 1])
with col1:
    origin = st.text_input("Enter a location name", "Alkapuri Tiraha", label_visibility="collapsed")
with col2:
    origin_pincode = st.text_input("Pincode (Optional)", "", max_chars=6, label_visibility="collapsed")

st.subheader("🏁 End Location")
col3, col4 = st.columns([3, 1])
with col3:
    destination = st.text_input("Enter a location name", "Gwalior Railway Station", key="dest_name", label_visibility="collapsed")
with col4:
    destination_pincode = st.text_input("Pincode (Optional)", "", max_chars=6, key="dest_pincode", label_visibility="collapsed")

if st.button("Get Forecasts", disabled=(not WEATHER_API_KEY or not TOMTOM_API_KEY), use_container_width=True):
    with st.spinner("Analyzing routes and live conditions..."):
        start_coords = get_coordinates(TOMTOM_API_KEY, origin, origin_pincode)
        end_coords = get_coordinates(TOMTOM_API_KEY, destination, destination_pincode)

        if not start_coords or not end_coords:
            st.error("Could not find one or both locations. Please be more specific or check the pincode.")
        else:
            st.session_state.results = {}
            
            # Car Prediction (using our ML Model)
            base_time, route_geometry = get_route_details(TOMTOM_API_KEY, start_coords, end_coords, mode='car')
            if base_time and base_time < 10800:
                now_ist = datetime.now(IST)
                # ... (rest of the prediction logic remains the same)
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
                st.session_state.results['car'] = predicted_seconds[0] / 60
                st.session_state.results['route_geometry'] = route_geometry
                st.session_state.results['weather_desc'] = weather_desc
            
            # Other travel mode predictions
            moto_time, _ = get_route_details(TOMTOM_API_KEY, start_coords, end_coords, mode='motorcycle')
            if moto_time: st.session_state.results['motorcycle'] = moto_time / 60
            walk_time, _ = get_route_details(TOMTOM_API_KEY, start_coords, end_coords, mode='pedestrian')
            if walk_time: st.session_state.results['pedestrian'] = walk_time / 60

# --- Display Results ---
if 'results' in st.session_state and st.session_state.results:
    results = st.session_state.results
    st.subheader("Travel Time Forecasts")
    
    res_col1, res_col2, res_col3 = st.columns(3)
    # ... (rest of the display logic remains the same)
    with res_col1:
        if 'car' in results: st.metric(label="🚗 By Car (AI Forecast)", value=f"{results['car']:.0f} min")
    with res_col2:
        if 'motorcycle' in results: st.metric(label="🏍️ By 2-Wheeler (Live API)", value=f"{results['motorcycle']:.0f} min")
    with res_col3:
        if 'pedestrian' in results: st.metric(label="🚶 By Walking (Live API)", value=f"{results['pedestrian']:.0f} min")
    st.info(f"**Live Conditions:** {datetime.now(IST).strftime('%I:%M %p, %A')}, {results.get('weather_desc', 'Weather data unavailable')}")

    if results.get('route_geometry'):
        st.subheader("Recommended Route Map")
        # FIX: Change map style to a more detailed one
        m = folium.Map(location=[GWALIOR_LAT, GWALIOR_LON], zoom_start=13, tiles='CartoDB positron')
        folium.PolyLine(results['route_geometry'], color="#0078FF", weight=7, opacity=0.8).add_to(m)
        
        start_lat, start_lon = map(float, start_coords.split(','))
        end_lat, end_lon = map(float, end_coords.split(','))
        folium.Marker([start_lat, start_lon], popup=f"Start: {origin}", icon=folium.Icon(color='green', icon='play')).add_to(m)
        folium.Marker([end_lat, end_lon], popup=f"End: {destination}", icon=folium.Icon(color='red', icon='stop')).add_to(m)
        
        # Auto-zoom the map to fit the route
        m.fit_bounds([[start_lat, start_lon], [end_lat, end_lon]])
        
        st_folium(m, width="100%", height=500, returned_objects=[])
