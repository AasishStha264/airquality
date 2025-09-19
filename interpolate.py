from scipy.interpolate import griddata
import numpy as np
import pandas as pd

def interpolate_idw(data, grid_resolution=0.05, power=2.0):
    """
    Perform Inverse Distance Weighting (IDW) interpolation for PM2.5 values.
    
    Parameters:
    - data: pd.DataFrame with columns 'lon', 'lat', 'value'
    - grid_resolution: float, spacing for the output grid
    - power: float, power parameter for IDW (higher = more local influence)
    
    Returns:
    - grid_lon, grid_lat: 2D meshes
    - grid_values: 2D array of interpolated values (NaN outside influence)
    """
    if data.empty or len(data) < 3:  # Skip interpolation if < 3 points
        print("Warning: Fewer than 3 stations; skipping interpolation.")
        return None, None, None
    
    # Create grid slightly larger than data extent
    lon_min, lon_max = data['lon'].min() - 0.1, data['lon'].max() + 0.1
    lat_min, lat_max = data['lat'].min() - 0.1, data['lat'].max() + 0.1
    lons = np.arange(lon_min, lon_max, grid_resolution)
    lats = np.arange(lat_min, lat_max, grid_resolution)
    grid_lon, grid_lat = np.meshgrid(lons, lats)

    # Station points and values
    points = data[['lon', 'lat']].values  # (n_stations, 2): [lon, lat]
    values = data['value'].values

    # Initialize grid with NaN
    grid_values = np.full_like(grid_lon, np.nan)

    # IDW interpolation for each grid point
    for i in range(grid_lat.shape[0]):
        for j in range(grid_lon.shape[1]):
            query_lon = grid_lon[i, j]
            query_lat = grid_lat[i, j]
            
            # Compute distances (in degrees, approximate for small areas)
            dists = np.sqrt((points[:, 0] - query_lon)**2 + (points[:, 1] - query_lat)**2)
            
            # Avoid division by zero (exact station location)
            dists[dists == 0] = np.finfo(float).eps
            
            # Weights: 1 / dist^power
            weights = 1.0 / (dists ** power)
            
            # Weighted average
            grid_values[i, j] = np.sum(weights * values) / np.sum(weights)

    return grid_lon, grid_lat, grid_values

def interpolate_idw_point(data, query_lon, query_lat, power=2.0):
    """
    Perform IDW interpolation for a single point.
    
    Parameters:
    - data: pd.DataFrame with columns 'lon', 'lat', 'value'
    - query_lon, query_lat: coordinates of the point to interpolate
    - power: float, power parameter for IDW
    
    Returns:
    - interpolated_value: float or NaN if insufficient data
    """
    if data.empty or len(data) < 3:
        return np.nan
    
    points = data[['lon', 'lat']].values
    values = data['value'].values
    
    dists = np.sqrt((points[:, 0] - query_lon)**2 + (points[:, 1] - query_lat)**2)
    dists[dists == 0] = np.finfo(float).eps
    weights = 1.0 / (dists ** power)
    interpolated_value = np.sum(weights * values) / np.sum(weights)
    
    return interpolated_value