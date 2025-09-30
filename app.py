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
GAZETTEER_PATH = "data/gwalior_locations.csv"
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

@st.cache_data
def load_gazetteer(path):
    try:
        df = pd.read_csv(path)
        return {row['alias'].upper(): row['official_search_query'] for index, row in df.iterrows()}
    except FileNotFoundError:
        return {} 

model = load_model(MODEL_PATH)
known_locations = load_gazetteer(GAZETTEER_PATH)

# --- LIVE DATA API FUNCTIONS ---

@st.cache_data(ttl=600)
def get_live_weather(api_key, lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
    try:
        response = requests.get(url).json()
        weather_main = response['weather'][0]['main']
        if 'Rain' in weather_main or 'Drizzle' in weather_main or 'Thunderstorm' in weather_main: return 2, f"Rainy 🌧️ ({weather_main})"
        elif 'Clouds' in weather_main: return 1, f"Cloudy ☁️ ({weather_main})"
        else: return 0, f"Clear ☀️ ({weather_main})"
    except Exception: return 0, "Clear ☀️ (default)"

@st.cache_data(ttl=3600)
def get_location_options(api_key, location_name, pincode=None):
    search_query = f"{location_name}, Gwalior, India"
    if pincode and len(pincode) == 6 and pincode.isdigit():
        search_query = f"{location_name}, {pincode}, Gwalior, India"
    encoded_location = quote(search_query)
    url = f"https://api.tomtom.com/search/2/search/{encoded_location}.json?key={api_key}&lat={GWALIOR_LAT}&lon={GWALIOR_LON}&limit=5"
    try:
        response = requests.get(url).json()
        if response and response['results']:
            return {res['address']['freeformAddress']: f"{res['position']['lat']},{res['position']['lon']}" for res in response['results']}
    except Exception as e:
        st.error(f"Error searching for location '{location_name}': {e}")
    return {}

@st.cache_data(ttl=60)
def get_route_details(api_key, start_coords, end_coords, mode='car'):
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{start_coords}:{end_coords}/json?key={api_key}&travelMode={mode}&traffic=true&routeType=fastest&routeRepresentation=polyline"
    try:
        response = requests.get(url).json()
        if 'routes' in response and len(response['routes']) > 0:
            route = response['routes'][0]
            summary = route['summary']
            
            # --- FIX: Gracefully handle missing traffic data during off-peak hours ---
            live_time = summary.get('trafficTravelTimeInSeconds', summary.get('travelTimeInSeconds'))
            base_time = summary.get('travelTimeInSeconds')
            
            points = route['legs'][0]['points']
            route_geometry = [[p['latitude'], p['longitude']] for p in points]
            
            if live_time and base_time:
                return live_time, base_time, route_geometry
    except Exception as e:
        # This will now display the actual API error on the screen for better debugging
        st.error(f"Error calculating route for '{mode}': {e}")
    return None, None, None

def get_traffic_status(predicted_time, base_time):
    if not base_time or base_time == 0: return "Unknown", "⚪"
    ratio = predicted_time / base_time
    if ratio < 1.2: return "Light Traffic", "🟢"
    elif 1.2 <= ratio < 1.6: return "Moderate Traffic", "🟡"
    else: return "Heavy Traffic", "🔴"

# --- STREAMLIT APP INTERFACE ---

st.title("🚗 Gwalior Smart Traffic Forecaster")

if 'stage' not in st.session_state:
    st.session_state.stage = 'search'

WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", "")
TOMTOM_API_KEY = st.secrets.get("TOMTOM_API_KEY", "")

if st.session_state.stage == 'search':
    st.write("Enter a start and end location in Gwalior to get a traffic forecast.")
    st.subheader("📍 Start Location")
    col1, col2 = st.columns([3, 1])
    with col1:
        origin = st.text_input("Enter a location name", "ITM University")
    with col2:
        origin_pincode = st.text_input("Pincode (Optional)", "474001", max_chars=6)
    st.subheader("🏁 End Location")
    col3, col4 = st.columns([3, 1])
    with col3:
        destination = st.text_input("Enter a location name", "Gwalior Railway Station")
    with col4:
        destination_pincode = st.text_input("Pincode (Optional)", "", max_chars=6)
    if st.button("Find Locations", use_container_width=True, disabled=(not TOMTOM_API_KEY)):
        with st.spinner("Searching for locations..."):
            origin_query = known_locations.get(origin.upper(), origin)
            destination_query = known_locations.get(destination.upper(), destination)
            st.session_state.origin_options = get_location_options(TOMTOM_API_KEY, origin_query, origin_pincode)
            st.session_state.destination_options = get_location_options(TOMTOM_API_KEY, destination_query, destination_pincode)
            st.session_state.user_inputs = {'origin': origin, 'destination': destination}
            if st.session_state.origin_options and st.session_state.destination_options:
                st.session_state.stage = 'confirm'
                st.rerun()
            else:
                st.error("Could not find one or both locations. Please be more specific.")

if st.session_state.stage == 'confirm':
    st.subheader("2. Confirm Your Locations")
    st.write("**Select the correct start location:**")
    confirmed_origin_address = st.radio("Origin Options", list(st.session_state.origin_options.keys()), label_visibility="collapsed")
    st.write("**Select the correct end location:**")
    confirmed_destination_address = st.radio("Destination Options", list(st.session_state.destination_options.keys()), label_visibility="collapsed")
    if st.button("Get Forecasts", use_container_width=True):
        st.session_state.start_coords = st.session_state.origin_options[confirmed_origin_address]
        st.session_state.end_coords = st.session_state.destination_options[confirmed_destination_address]
        st.session_state.stage = 'predict'
        st.rerun()
    if st.button("Start Over", use_container_width=True):
        st.session_state.stage = 'search'
        if 'results' in st.session_state: del st.session_state['results']
        st.rerun()

if st.session_state.stage == 'predict':
    start_coords = st.session_state.start_coords
    end_coords = st.session_state.end_coords
    
    results = {}
    now_ist = datetime.now(IST)
    weather_code, weather_desc = get_live_weather(WEATHER_API_KEY, GWALIOR_LAT, GWALIOR_LON)
    
    live_car_time, base_time, route_geometry = get_route_details(TOMTOM_API_KEY, start_coords, end_coords, mode='car')
    if base_time:
        prediction_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
        prediction_df.loc[0, ['base_travel_time_seconds', 'day_of_week', 'hour_of_day']] = [base_time, now_ist.weekday(), now_ist.hour]
        prediction_df.loc[0, 'is_market_closed'] = 1 if now_ist.weekday() == 1 else 0
        prediction_df.loc[0, 'is_holiday'] = 1 if now_ist.date() in indian_holidays else 0
        prediction_df.loc[0, 'weather'] = weather_code
        prediction_df.loc[0, 'route_name_Thatipur-to-Morar'] = 1
        predicted_seconds = model.predict(prediction_df)
        results['car_ml'] = predicted_seconds[0] / 60
        traffic_status_text, traffic_status_emoji = get_traffic_status(predicted_seconds[0], base_time)
        results['traffic_status'] = f"{traffic_status_text} {traffic_status_emoji}"
    
    moto_time, _, _ = get_route_details(TOMTOM_API_KEY, start_coords, end_coords, mode='motorcycle')
    if moto_time: results['motorcycle'] = moto_time / 60
    walk_time, _, _ = get_route_details(TOMTOM_API_KEY, start_coords, end_coords, mode='pedestrian')
    if walk_time: results['pedestrian'] = walk_time / 60
    
    st.subheader("Your Route")
    st.markdown(f"**From:** `{st.session_state.user_inputs['origin']}`  \n**To:** `{st.session_state.user_inputs['destination']}`")
    st.subheader("Live Forecast")
    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    with res_col1: st.metric(label="Traffic Status", value=results.get('traffic_status', 'N/A'))
    with res_col2: st.metric(label="🚗 By Car (AI)", value=f"{results.get('car_ml', 0):.0f} min")
    with res_col3: st.metric(label="🏍️ By 2-Wheeler", value=f"{results.get('motorcycle', 0):.0f} min")
    with res_col4: st.metric(label="🚶 By Walking", value=f"{results.get('pedestrian', 0):.0f} min")
    st.info(f"**Live Conditions:** {now_ist.strftime('%I:%M %p, %A')}, {weather_desc}")

    if route_geometry:
        st.subheader("Route Map")
        google_maps_tile = 'http://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}'
        m = folium.Map(location=[GWALIOR_LAT, GWALIOR_LON], zoom_start=13, tiles=google_maps_tile, attr='Google')
        folium.PolyLine(route_geometry, color="#0055FF", weight=7, opacity=0.8).add_to(m)
        start_lat, start_lon = map(float, start_coords.split(','))
        end_lat, end_lon = map(float, end_coords.split(','))
        folium.Marker([start_lat, start_lon], icon=folium.Icon(color='green', icon='play')).add_to(m)
        folium.Marker([end_lat, end_lon], icon=folium.Icon(color='red', icon='stop')).add_to(m)
        m.fit_bounds([[start_lat, start_lon], [end_lat, end_lon]])
        st_folium(m, width="100%", height=500, returned_objects=[])

    if st.button("New Search", use_container_width=True):
        st.session_state.stage = 'search'
        st.rerun()
