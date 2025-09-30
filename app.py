import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
import holidays
import requests

# --- CONFIGURATION & MODEL LOADING ---

# Path to your saved model
MODEL_PATH = "models/traffic_model.joblib"

# Gwalior's coordinates for the weather API
GWALIOR_LAT = 26.2183
GWALIOR_LON = 78.1828

# Get Indian holidays for the current year
indian_holidays = holidays.India(state='MP', years=datetime.now().year)

# Define the columns our model was trained on, in the exact same order
MODEL_COLUMNS = [
    'base_travel_time_seconds', 'day_of_week', 'hour_of_day',
    'is_market_closed', 'is_holiday', 'weather',
    'route_name_CityCenter-to-Palace', 'route_name_Fort-to-Station',
    'route_name_Highway-Bypass', 'route_name_Mall-to-IIITM',
    'route_name_Thatipur-to-Morar'
]

# Define our known routes
ROUTES = {
    'Fort-to-Station': 720,
    'CityCenter-to-Palace': 480,
    'Thatipur-to-Morar': 540,
    'Mall-to-IIITM': 660,
    'Highway-Bypass': 900
}

# Use Streamlit's cache to load the model only once
@st.cache_resource
def load_model(path):
    return joblib.load(path)

model = load_model(MODEL_PATH)

# --- LIVE DATA FUNCTIONS ---

def get_live_weather(api_key, lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
    try:
        response = requests.get(url)
        data = response.json()
        weather_main = data['weather'][0]['main']
        if 'Rain' in weather_main or 'Drizzle' in weather_main or 'Thunderstorm' in weather_main:
            return 2, "Rainy 🌧️"
        elif 'Clouds' in weather_main:
            return 1, "Cloudy ☁️"
        else:
            return 0, "Clear ☀️"
    except Exception:
        return 0, "Clear ☀️ (default)"

# --- STREAMLIT APP INTERFACE ---

st.set_page_config(page_title="Gwalior Traffic Forecaster", page_icon="🚗")
st.title("🚗 Gwalior Real-Time Traffic Forecaster")
st.write("This app uses a machine learning model to predict travel time on key routes in Gwalior based on live conditions.")

# Get Weather API key from the user (using Streamlit secrets for deployment)
WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", "")
if not WEATHER_API_KEY:
    WEATHER_API_KEY = st.text_input("Enter your OpenWeatherMap API Key to begin", type="password")

# User inputs
selected_route = st.selectbox("Select a Route:", list(ROUTES.keys()))

if st.button("Predict Travel Time"):
    if not WEATHER_API_KEY:
        st.error("Please enter your OpenWeatherMap API key to get a prediction.")
    else:
        with st.spinner("Fetching live data and making a prediction..."):
            # Get live features
            now = datetime.now()
            current_hour = now.hour
            current_day_of_week = now.weekday()
            is_market_closed = 1 if current_day_of_week == 1 else 0
            is_holiday = 1 if now.date() in indian_holidays else 0
            weather_code, weather_desc = get_live_weather(WEATHER_API_KEY, GWALIOR_LAT, GWALIOR_LON)
            base_time = ROUTES[selected_route]

            # Assemble feature vector
            prediction_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
            prediction_df['base_travel_time_seconds'] = base_time
            prediction_df['day_of_week'] = current_day_of_week
            prediction_df['hour_of_day'] = current_hour
            prediction_df['is_market_closed'] = is_market_closed
            prediction_df['is_holiday'] = is_holiday
            prediction_df['weather'] = weather_code
            route_column_name = f"route_name_{selected_route}"
            if route_column_name in prediction_df.columns:
                prediction_df[route_column_name] = 1

            # Make prediction
            predicted_seconds = model.predict(prediction_df)
            predicted_minutes = predicted_seconds[0] / 60

            # Display results
            st.success(f"**Estimated Travel Time: {predicted_minutes:.2f} minutes**")
            st.info(f"**Live Conditions:** Time: {now.strftime('%H:%M')}, Day: {now.strftime('%A')}, Weather: {weather_desc}")