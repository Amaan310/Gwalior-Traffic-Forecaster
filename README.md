# Gwalior-Traffic-Forecaster 🚗

A **location-based smart traffic prediction system** built using **Streamlit**, designed to estimate **real-time traffic conditions and travel time** between two locations in **Gwalior, Madhya Pradesh**.  
The application helps users make **better route and travel decisions** by visualizing traffic status and routes interactively on a map.

🔗 **Live App:** https://gwalior-traffic-forecaster.streamlit.app

---

## 📌 Project Overview

The **Gwalior Smart Traffic Forecaster** allows users to:
- Enter a **start and end location** within Gwalior
- Confirm the **correct geocoded locations**
- View **traffic intensity**, **estimated travel time**, and **route visualization**
- Compare travel duration across **multiple transport modes**

This project demonstrates the **real-world application of data, APIs, and interactive visualization** for smart city use cases.

---

## ⚙️ Key Features

- 📍 **Location Search & Validation**
  - Smart geocoding with multiple address suggestions
  - User confirmation for accurate route selection

- 🚦 **Live Traffic Status**
  - Displays traffic conditions (e.g., *Heavy Traffic*)
  - Context-aware indicators for congestion

- ⏱️ **Travel Time Estimation**
  - 🚗 Car
  - 🛵 Two-Wheeler
  - 🚶 Walking

- 🗺️ **Interactive Route Map**
  - Visual route plotting using maps
  - Start & end markers with clear navigation paths

- 🔄 **Multi-Step User Flow**
  - Search → Confirm → Forecast → New Search

---

## 🧠 Tech Stack Used

- **Frontend / UI:** Streamlit  
- **Backend Logic:** Python  
- **Maps & Visualization:** Folium / Leaflet  
- **Geocoding & Location Services:** OpenStreetMap APIs  
- **Deployment:** Streamlit Cloud  

---

## 🧩 How It Works

1. User enters **start & end locations**
2. System fetches **multiple matching locations**
3. User confirms the correct locations
4. Traffic conditions and travel time are calculated
5. Route is visualized on an **interactive map**
6. Users can restart and try different routes

---

## 📊 Use Cases

- 🚕 Daily commuting route analysis  
- 🏙️ Smart city traffic insights  
- 🚦 Urban traffic planning (basic prototype)

---

## 📁 Repository Structure
Gwalior-Traffic-Forecaster/
│
├── app.py               # Main Streamlit application
├── requirements.txt     # Project dependencies
├── README.md            # Project documentation

---

## 🎯 Future Enhancements

- 🔮 ML-based traffic prediction using historical + live data

- 📊 Traffic trend analysis by time, day, and route

- 🌧️ Weather-aware traffic forecasting

- 📱 Mobile-responsive UI improvements

- 🧠 AI-powered optimal route recommendation

- 🗺️ Support for multi-city traffic forecasting
