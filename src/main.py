from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from datetime import datetime, timedelta
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Resolve the base directory and load environment variables (OPENELECTRICITY_API_KEY)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Import our API Clients
from src.api_clients.pricing_api import OpenNEMClient
from src.api_clients.open_meteo import OpenMeteoClient

app = FastAPI(title="Energy Arbitrage API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_settings():
    """Helper function to parse configuration limits and location data."""
    settings_path = BASE_DIR / "config" / "settings.yaml"
    try:
        with open(settings_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Could not load settings.yaml: {e}")
        # Fallback defaults if the yaml file is missing or unreadable
        return {
            "location": {"latitude": -33.8688, "longitude": 151.2093},
            "market": {"nem_region": "NSW1"}
        }

@app.get("/api/v1/market-data")
def get_market_data():
    """
    Fetches live data from OpenElectricity and Open-Meteo, merges them 
    into a synchronized 30-minute time-series DataFrame, and returns JSON.
    """
    settings = load_settings()
    nem_region = settings["market"]["nem_region"]
    lat = settings["location"]["latitude"]
    lon = settings["location"]["longitude"]
    
    try:
        # 1. Fetch Real Pricing Data (Last 2 days to keep the API fast)
        pricing_client = OpenNEMClient()
        df_price = pricing_client.get_regional_energy_data(nem_region, days=2)
        
        # 2. Fetch Real Weather Data
        meteo_client = OpenMeteoClient()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)
        df_weather = meteo_client.get_historical_weather_df(
            latitude=lat,
            longitude=lon,
            start_date=start_date.strftime("%Y-%m-%d"), 
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        # 3. Standardize and Process Price Data
        if df_price is not None and not df_price.empty:
            df_price = df_price.reset_index()
            
            # Map OE columns to our standardized naming convention
            col_map = {col: 'timestamp' for col in df_price.columns if 'interval' in str(col).lower() or 'time' in str(col).lower()}
            col_map.update({col: 'spot_price' for col in df_price.columns if 'value' in str(col).lower() or 'price' in str(col).lower()})
            col_map.update({col: 'demand' for col in df_price.columns if 'demand' in str(col).lower()})

            df_price = df_price.rename(columns=col_map)
            df_price['timestamp'] = pd.to_datetime(df_price['timestamp'], utc=True)
            df_price = df_price.set_index('timestamp')
            
            # Clean duplicates and resample explicitly to 30 minutes
            df_price = df_price[~df_price.index.duplicated()]
            cols_to_resample = [c for c in df_price.columns if c in ['spot_price', 'demand', 'renewable_generation', 'interconnector_flow_mw'] or c.startswith('gen_')]
            if cols_to_resample:
                df_price = df_price[cols_to_resample].resample('30min').mean()
        else:
            df_price = pd.DataFrame()

        # 4. Standardize and Process Weather Data
        if df_weather is not None and not df_weather.empty:
            df_weather['timestamp'] = pd.to_datetime(df_weather['timestamp'], utc=True)
            df_weather = df_weather.set_index('timestamp')
            
            # Weather is hourly, so we forward-fill to get it to our 30-min target interval
            df_weather = df_weather.resample('30min').ffill()
        else:
            df_weather = pd.DataFrame()

        # 5. Merge Both Datasets Chronologically
        df_merged = pd.merge(df_price, df_weather, left_index=True, right_index=True, how='inner')
        
        # Convert datetime index back to ISO strings and fill any nulls before passing to React
        df_merged = df_merged.reset_index()
        df_merged['timestamp'] = df_merged['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        df_merged = df_merged.fillna(0)

        return df_merged.to_dict(orient="records")

    except Exception as e:
        print(f"Data pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/map-data")
def get_map_data():
    """
    Fetches the recent demand and price across all NEM regions to power the frontend geospatial map.
    Returns the full recent window (e.g., 2 hours) to support timeline slider interactions.
    """
    try:
        pricing_client = OpenNEMClient()
        df = pricing_client.get_latest_nem_demand()
        
        if df is not None and not df.empty:
            # Return the full 2-hour dataset to allow React to scrub through the timeline
            df = df.sort_values(['interval', 'network_region'])
            return df.fillna(0).to_dict(orient="records")
            
        return []
    except Exception as e:
        print(f"Map data pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))