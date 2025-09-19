import folium
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from io import BytesIO
import base64

def create_map(grid_lon, grid_lat, grid_values, data, bbox, center=None):
    # Define legend HTML with dynamic sizing
    legend_html = '''
    <div style="background-color: white; border: 2px solid grey; 
                font-size: 12px; padding: 10px; border-radius: 5px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.2); width: auto; height: auto; 
                display: inline-block;">
    <h4 style="margin: 0 0 8px 0; padding: 0; text-align: center;">AQI Levels & Effects</h4>
    <p style="margin: 4px 0;"><span style="color: green; font-size: 16px;">●</span> Good (0-50): Little to no health risks</p>
    <p style="margin: 4px 0;"><span style="color: yellow; font-size: 16px;">●</span> Moderate (51-100): Minor effects for sensitive groups</p>
    <p style="margin: 4px 0;"><span style="color: orange; font-size: 16px;">●</span> Unhealthy for Sensitive (101-150): Limit activity for vulnerable</p>
    <p style="margin: 4px 0;"><span style="color: red; font-size: 16px;">●</span> Unhealthy (151+): Effects for all; avoid exertion</p>
    </div>
    '''
    
    # Default map if no data or insufficient points for interpolation
    if data.empty or grid_lon is None or grid_values is None or np.all(np.isnan(grid_values)):
        m = folium.Map(location=[27.7, 85.3], zoom_start=7, tiles='OpenStreetMap')  # Center on Kathmandu
        if data.empty:
            folium.Marker([27.7, 85.3], popup="No data available").add_to(m)
        else:
            # Add markers for available stations with detailed popups
            def get_color(aqi):
                if aqi <= 50: return 'green'
                elif aqi <= 100: return 'yellow'
                elif aqi <= 150: return 'orange'
                else: return 'red'

            def get_alert(aqi):
                if aqi <= 50:
                    return "🟢 Good: Air quality is satisfactory. No health risks."
                elif aqi <= 100:
                    return "🟡 Moderate: Air quality acceptable. Sensitive groups may notice minor effects."
                elif aqi <= 150:
                    return "🟠 Unhealthy for Sensitive: Reduce outdoor activity for children, elderly, and those with respiratory issues."
                else:
                    return "🔴 Unhealthy: Potential health effects for everyone. Limit outdoor time."

            for _, row in data.iterrows():
                aqi = row.get('aqi', 0)
                pm25 = row.get('value', 0)
                station_name = row.get('station_name', 'Unknown Station')
                timestamp = row.get('datetime', 'Unknown Time')
                popup_content = f"""
                <div style="font-size: 12px; padding: 5px; width: 200px;">
                    <b>Station: {station_name}</b><br>
                    <b>AQI: {aqi}</b><br>
                    PM2.5: {pm25:.1f} µg/m³<br>
                    {get_alert(aqi)}<br>
                    Lat: {row['lat']:.3f}<br>
                    Lon: {row['lon']:.3f}<br>
                    Time: {timestamp}<br>
                </div>
                """
                folium.CircleMarker(
                    location=[float(row['lat']), float(row['lon'])],
                    radius=6, 
                    color=get_color(aqi), 
                    fill=True, 
                    fillOpacity=0.8,
                    popup=folium.Popup(popup_content, max_width=200)
                ).add_to(m)
        # Fit to bbox
        bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
        m.fit_bounds(bounds)
        
        return m, legend_html

    # Normal case with interpolation: Create smooth colored overlay
    if center is None:
        center = [grid_lat.mean(), grid_lon.mean()]

    m = folium.Map(location=center, zoom_start=7, tiles='OpenStreetMap')

    # Validate grid_values for contour plotting
    valid_values = grid_values[~np.isnan(grid_values)]
    if len(valid_values) == 0:
        # No valid interpolated data; fallback to markers
        def get_color(aqi):
            if aqi <= 50: return 'green'
            elif aqi <= 100: return 'yellow'
            elif aqi <= 150: return 'orange'
            else: return 'red'

        def get_alert(aqi):
            if aqi <= 50:
                return "🟢 Good: Air quality is satisfactory. No health risks."
            elif aqi <= 100:
                return "🟡 Moderate: Air quality acceptable. Sensitive groups may notice minor effects."
            elif aqi <= 150:
                return "🟠 Unhealthy for Sensitive: Reduce outdoor activity for children, elderly, and those with respiratory issues."
            else:
                return "🔴 Unhealthy: Potential health effects for everyone. Limit outdoor time."

        for _, row in data.iterrows():
            aqi = row.get('aqi', 0)
            pm25 = row.get('value', 0)
            station_name = row.get('station_name', 'Unknown Station')
            timestamp = row.get('datetime', 'Unknown Time')
            popup_content = f"""
            <div style="font-size: 12px; padding: 5px; width: 200px;">
                <b>Station: {station_name}</b><br>
                <b>AQI: {aqi}</b><br>
                PM2.5: {pm25:.1f} µg/m³<br>
                {get_alert(aqi)}<br>
                Lat: {row['lat']:.3f}<br>
                Lon: {row['lon']:.3f}<br>
                Time: {timestamp}<br>
            </div>
            """
            folium.CircleMarker(
                location=[float(row['lat']), float(row['lon'])],
                radius=6, 
                color=get_color(aqi), 
                fill=True, 
                fillOpacity=0.8,
                popup=folium.Popup(popup_content, max_width=200)
            ).add_to(m)
        # Fit to bbox
        bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
        m.fit_bounds(bounds)
        
        return m, legend_html

    # Generate filled contour image with smooth colors
    fig, ax = plt.subplots(figsize=(10, 10))
    # PM2.5 levels for AQI categories: Good (<12), Moderate (12-35.4), Unhealthy Sensitive (35.5-55.4), Unhealthy (>55.4)
    max_value = max(np.max(valid_values), 55.4) + 1 if len(valid_values) > 0 else 200
    levels = [0, 12, 35.4, 55.4, max_value]  # Strictly increasing, finite levels
    colors = ['green', 'yellow', 'orange', 'red']
    cmap = ListedColormap(colors)
    
    # Filled contours (smooth areas, no boundary lines)
    cf = ax.contourf(grid_lon, grid_lat, grid_values, levels=levels, cmap=cmap, extend='max', alpha=0.6)
    
    # Remove axes, set extent
    ax.set_xlim(grid_lon.min(), grid_lon.max())
    ax.set_ylim(grid_lat.min(), grid_lat.max())
    ax.axis('off')
    
    # Save as transparent PNG
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=150, facecolor='none')
    buf.seek(0)
    img_data = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    # Overlay image on Folium
    img_bounds = [[grid_lat.min(), grid_lon.min()], [grid_lat.max(), grid_lon.max()]]
    folium.raster_layers.ImageOverlay(
        image=f'data:image/png;base64,{img_data}',
        bounds=img_bounds,
        opacity=0.7
    ).add_to(m)
    
    # Station markers with detailed popups
    def get_color(aqi):
        if aqi <= 50: return 'green'
        elif aqi <= 100: return 'yellow'
        elif aqi <= 150: return 'orange'
        else: return 'red'

    def get_alert(aqi):
        if aqi <= 50:
            return "🟢 Good: Air quality is satisfactory. No health risks."
        elif aqi <= 100:
            return "🟡 Moderate: Air quality acceptable. Sensitive groups may notice minor effects."
        elif aqi <= 150:
            return "🟠 Unhealthy for Sensitive: Reduce outdoor activity for children, elderly, and those with respiratory issues."
        else:
            return "🔴 Unhealthy: Potential health effects for everyone. Limit outdoor time."

    for _, row in data.iterrows():
        aqi = row.get('aqi', 0)
        pm25 = row.get('value', 0)
        station_name = row.get('station_name', 'Unknown Station')
        timestamp = row.get('datetime', 'Unknown Time')
        popup_content = f"""
        <div style="font-size: 12px; padding: 5px; width: 200px;">
            <b>Station: {station_name}</b><br>
            <b>AQI: {aqi}</b><br>
            PM2.5: {pm25:.1f} µg/m³<br>
            {get_alert(aqi)}<br>
            Lat: {row['lat']:.3f}<br>
            Lon: {row['lon']:.3f}<br>
            Time: {timestamp}<br>
        </div>
        """
        folium.CircleMarker(
            location=[float(row['lat']), float(row['lon'])],
            radius=6, 
            color=get_color(aqi), 
            fill=True, 
            fillOpacity=0.8,
            popup=folium.Popup(popup_content, max_width=200)
        ).add_to(m)

    # Fit to bbox
    bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
    m.fit_bounds(bounds)

    return m, legend_html
