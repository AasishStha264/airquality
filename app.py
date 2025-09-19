import streamlit as st
import pandas as pd
import time
import numpy as np
from fetch_data import fetch_latest_pm25
from interpolate import interpolate_idw, interpolate_idw_point
from visualize import create_map
from streamlit_folium import st_folium
import folium
import json

# Predefined regions with bbox (min_lon, min_lat, max_lon, max_lat)
REGIONS = {
    "London, UK": (-0.5, 51.3, 0.3, 51.7),
    "Delhi, India": (76.8, 28.4, 77.4, 28.9),
    "New York City, USA": (-74.3, 40.5, -73.7, 40.9),
    "Houston, USA": (-95.8, 29.5, -95.0, 30.0),
}

# PM2.5 to AQI conversion (US EPA breakpoints)
@st.cache_data
def pm25_to_aqi(pm25):
    try:
        pm25 = float(pm25)
        if pm25 <= 12:
            return int((50 / 12) * pm25)
        elif pm25 <= 35.4:
            return int(50 + (50 / 23.4) * (pm25 - 12.1))
        elif pm25 <= 55.4:
            return int(100 + (50 / 20) * (pm25 - 35.5))
        elif pm25 <= 150.4:
            return int(150 + (50 / 95) * (pm25 - 55.5))
        else:
            return 201  # Simplified for >150.4 (Very Unhealthy+)
    except (ValueError, TypeError):
        return 0  # Fallback for invalid PM2.5 values

# Get AQI alert message
def get_aqi_alert(aqi):
    if aqi <= 50:
        return "🟢 Good: Air quality is satisfactory. No health risks."
    elif aqi <= 100:
        return "🟡 Moderate: Air quality acceptable. Sensitive groups may notice minor effects."
    elif aqi <= 150:
        return "🟠 Unhealthy for Sensitive: Reduce outdoor activity for children, elderly, and those with respiratory issues."
    else:
        return "🔴 Unhealthy: Potential health effects for everyone. Limit outdoor time."

# App setup
st.set_page_config(page_title="Live Air Quality Monitor", page_icon="🌤️", layout="wide")
st.title("🌤️ Live Air Quality Monitor (AQI based on PM2.5)")
st.markdown("*Updates every 5 minutes with latest data from OpenAQ server. Click anywhere on the map for interpolated AQI or on stations for detailed info!*")

# Sidebar for controls
with st.sidebar:
    st.header("📍 Region Selection")
    selected_region = st.selectbox("Select Region", list(REGIONS.keys()))
    bbox = REGIONS[selected_region]
    st.info(f"Selected: **{selected_region}**")
    # Placeholder for legend
    legend_placeholder = st.empty()

# Config
REFRESH_INTERVAL = 300  # seconds

# Dynamically adjust grid resolution based on bbox size
lon_span = bbox[2] - bbox[0]
lat_span = bbox[3] - bbox[1]
area_span = max(lon_span, lat_span)
if area_span < 1:  # Small city/urban area
    grid_resolution = 0.005
elif area_span < 5:  # Medium region
    grid_resolution = 0.02
else:  # Large country/region
    grid_resolution = 0.05

# Session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = 0
    st.session_state.map = None
    st.session_state.data = pd.DataFrame()
    st.session_state.selected_region = None
    st.session_state.grid_lon = None
    st.session_state.grid_lat = None
    st.session_state.grid_values = None

# Force refresh if region changes
if st.session_state.selected_region != selected_region:
    st.session_state.last_update = 0
    st.session_state.selected_region = selected_region

# Auto-refresh
update_time_str = None
legend_html = None
if time.time() - st.session_state.last_update > REFRESH_INTERVAL:
    with st.spinner(f"🔄 Fetching latest data from OpenAQ for {selected_region}..."):
        try:
            data = fetch_latest_pm25(bbox)
            if data.empty:
                st.error(f"❌ No data available for {selected_region}. Check API key or station availability.")
            else:
                # Compute AQI for stations
                data['aqi'] = data['value'].apply(pm25_to_aqi)
                grid_lon, grid_lat, grid_pm25 = interpolate_idw(data, grid_resolution=grid_resolution, power=2.0)
                if grid_lon is None or np.all(np.isnan(grid_pm25)):
                    st.warning(f"⚠️ Insufficient data for interpolation in {selected_region} (fewer than 3 stations or invalid data). Showing station markers only.")
                else:
                    st.success(f"✅ Interpolated PM2.5/AQI for {selected_region} using {len(data)} stations with IDW method.")
                m, legend_html = create_map(grid_lon, grid_lat, grid_pm25, data, bbox)
                
                # Add custom click handler for non-station popups
                if not data.empty:
                    # Prepare data for JavaScript (only for non-station clicks)
                    stations = data[['lon', 'lat', 'value']].to_dict('records')
                    js_code = """
                    <script>
                    function addClickHandler(map) {
                        try {
                            map.on('click', function(e) {
                                // Check if click is on a marker (skip if true to allow marker popups)
                                if (e.originalEvent.target.className.includes('marker')) {
                                    return;
                                }
                                var lat = e.latlng.lat;
                                var lng = e.latlng.lng;
                                var stations = %s;
                                var power = 2.0;
                                var sum_weights = 0;
                                var sum_weighted_values = 0;
                                for (var i = 0; i < stations.length; i++) {
                                    var dist = Math.sqrt(
                                        Math.pow(stations[i].lon - lng, 2) +
                                        Math.pow(stations[i].lat - lat, 2)
                                    );
                                    if (dist === 0) dist = Number.EPSILON;
                                    var weight = 1 / Math.pow(dist, power);
                                    sum_weights += weight;
                                    sum_weighted_values += weight * stations[i].value;
                                }
                                var pm25 = sum_weighted_values / sum_weights;
                                var aqi;
                                if (pm25 <= 12) {
                                    aqi = Math.round((50 / 12) * pm25);
                                } else if (pm25 <= 35.4) {
                                    aqi = Math.round(50 + (50 / 23.4) * (pm25 - 12.1));
                                } else if (pm25 <= 55.4) {
                                    aqi = Math.round(100 + (50 / 20) * (pm25 - 35.5));
                                } else if (pm25 <= 150.4) {
                                    aqi = Math.round(150 + (50 / 95) * (pm25 - 55.5));
                                } else {
                                    aqi = 201;
                                }
                                var alert;
                                if (aqi <= 50) {
                                    alert = "🟢 Good: Air quality is satisfactory. No health risks.";
                                } else if (aqi <= 100) {
                                    alert = "🟡 Moderate: Air quality acceptable. Sensitive groups may notice minor effects.";
                                } else if (aqi <= 150) {
                                    alert = "🟠 Unhealthy for Sensitive: Reduce outdoor activity for children, elderly, and those with respiratory issues.";
                                } else {
                                    alert = "🔴 Unhealthy: Potential health effects for everyone. Limit outdoor time.";
                                }
                                var content;
                                if (isNaN(pm25)) {
                                    content = '<div style="font-size: 12px; padding: 5px;">' +
                                              '<b>No data</b><br>' +
                                              'Lat: ' + lat.toFixed(3) + '<br>' +
                                              'Lon: ' + lng.toFixed(3) + '<br>' +
                                              '<i>Outside station coverage</i>' +
                                              '</div>';
                                } else {
                                    content = '<div style="font-size: 12px; padding: 5px;">' +
                                              '<b>AQI: ' + aqi + '</b><br>' +
                                              'PM2.5: ' + pm25.toFixed(1) + ' µg/m³<br>' +
                                              alert + '<br>' +
                                              'Lat: ' + lat.toFixed(3) + '<br>' +
                                              'Lon: ' + lng.toFixed(3) + '</div>';
                                }
                                L.popup()
                                 .setLatLng(e.latlng)
                                 .setContent(content)
                                 .openOn(map);
                            });
                        } catch (err) {
                            console.error("Error in click handler: " + err.message);
                        }
                    }
                    </script>
                    """ % json.dumps(stations)
                    m.get_root().html.add_child(folium.Element(js_code))
                    m.get_root().html.add_child(folium.Element("<script>document.addEventListener('DOMContentLoaded', function() { try { addClickHandler(map); } catch (err) { console.error('Error initializing click handler: ' + err.message); } });</script>"))
                
                st.session_state.map = m
                st.session_state.data = data
                st.session_state.grid_lon = grid_lon
                st.session_state.grid_lat = grid_lat
                st.session_state.grid_values = grid_pm25
                st.session_state.last_update = time.time()
                update_time_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(st.session_state.last_update))
        except Exception as e:
            st.error(f"❌ Error updating data: {e}")

# Display legend in sidebar
if legend_html:
    with legend_placeholder:
        st.markdown("**AQI Levels & Effects**")
        st.markdown(legend_html, unsafe_allow_html=True)

# Layout: Columns for map and data
col1, col2 = st.columns([7, 3])

with col1:
    st.subheader("🗺️ Interactive Air Quality Map")
    if st.session_state.map:
        st_folium(
            st.session_state.map,
            width=700,
            height=500,
            returned_objects=[]
        )
    else:
        st.info("🗺️ Select a region to load the map.")
    
    # Display update time
    if update_time_str:
        st.caption(f"**Last updated**: {update_time_str}")

with col2:
    st.subheader("📊 Quick Stats")
    if not st.session_state.data.empty:
        avg_pm25 = st.session_state.data['value'].mean()
        avg_aqi = st.session_state.data['aqi'].mean()
        num_stations = len(st.session_state.data)
        st.metric("Avg PM2.5 (µg/m³)", f"{avg_pm25:.1f}", delta=None)
        st.metric("Avg AQI", f"{avg_aqi:.0f}", delta=None)
        st.metric("Stations", num_stations, delta=None)
        
        # Overall average AQI message
        avg_alert = get_aqi_alert(avg_aqi)
        st.markdown(f"**Overall Alert**: {avg_alert}")
        
        with st.expander("🔍 Detailed Station Data (Current from OpenAQ)"):
            st.dataframe(st.session_state.data[['lat', 'lon', 'value', 'aqi', 'datetime']].round(2), use_container_width=True)
    else:
        st.info("No data loaded yet.")

# Manual refresh
if st.button("🔄 Refresh Now", type="primary"):
    st.session_state.last_update = 0
    st.rerun()

st.markdown("---")
st.info("🌐 *Data from OpenAQ server (latest PM2.5). AQI computed via US EPA formula. Click anywhere on the map for interpolated AQI or on stations for detailed info!*")