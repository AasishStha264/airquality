import requests
import pandas as pd
from dotenv import load_dotenv
import os

# Load API key
load_dotenv()
API_KEY = os.getenv('OPENAQ_API_KEY')
if not API_KEY:
    raise ValueError("API key not found in .env file")

PARAMETER_ID = '2'  # PM2.5
LIMIT = 1000  # Max results
BASE_URL = 'https://api.openaq.org/v3'

def fetch_latest_pm25(bbox=None):
    try:
        url = f'{BASE_URL}/parameters/{PARAMETER_ID}/latest?limit={LIMIT}'
        headers = {'X-API-Key': API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if 'results' not in data or not data['results']:
            return pd.DataFrame(columns=['lat', 'lon', 'value', 'datetime'])

        df = pd.DataFrame(data['results'])
        # Extract coordinates, value, datetime
        df['lat'] = df['coordinates'].apply(lambda x: x['latitude'] if isinstance(x, dict) else None)
        df['lon'] = df['coordinates'].apply(lambda x: x['longitude'] if isinstance(x, dict) else None)
        df['datetime'] = df['datetime'].apply(lambda x: x['utc'] if isinstance(x, dict) else None)
        df['value'] = df['value'].apply(lambda x: x if isinstance(x, (int, float)) else None)
        df = df[['lat', 'lon', 'value', 'datetime']].dropna()

        # Filter by bbox if provided
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            df = df[(df['lon'] >= min_lon) & (df['lon'] <= max_lon) &
                    (df['lat'] >= min_lat) & (df['lat'] <= max_lat)]
        
        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame(columns=['lat', 'lon', 'value', 'datetime'])

# Test
if __name__ == '__main__':
    nepal_bbox = (80.0, 26.0, 88.0, 30.5)  # Nepal
    data = fetch_latest_pm25(nepal_bbox)
    print(f"Fetched {len(data)} stations")
    print(data.head())
    data.to_csv('nepal_pm25.csv', index=False)