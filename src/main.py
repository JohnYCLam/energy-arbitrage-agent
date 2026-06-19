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
from src.config.locations import VICTORIA_WEATHER_LOCATIONS
from src.config.forecasting import load_forecasting_config
from src.models.align_timeseries import (
    align_energy_df,
    align_weather_df,
    merge_energy_weather,
    normalize_live_energy_df,
)

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
    into a synchronized time-series DataFrame at the configured forecast
    grid resolution, and returns JSON.
    """
    settings = load_settings()
    cfg = load_forecasting_config()
    nem_region = settings["market"]["nem_region"]
    lat = settings["location"]["latitude"]
    lon = settings["location"]["longitude"]

    try:
        pricing_client = OpenNEMClient()
        df_price = pricing_client.get_regional_energy_data(nem_region, days=2)

        meteo_client = OpenMeteoClient()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)
        df_weather = meteo_client.get_historical_weather_df(
            latitude=lat,
            longitude=lon,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )

        if df_price is not None and not df_price.empty:
            df_price = normalize_live_energy_df(df_price.reset_index(), cfg=cfg)
            df_price = align_energy_df(df_price, cfg, timestamp_col="timestamp")
        else:
            df_price = pd.DataFrame()

        if df_weather is not None and not df_weather.empty:
            df_weather = align_weather_df(df_weather, cfg)
        else:
            df_weather = pd.DataFrame()

        if df_price.empty or df_weather.empty:
            df_merged = pd.DataFrame()
        else:
            df_merged = merge_energy_weather(df_price, df_weather, cfg)

        if df_merged.empty:
            return []

        df_merged.index.name = "timestamp"
        df_merged = df_merged.reset_index()
        df_merged["timestamp"] = df_merged["timestamp"].apply(lambda ts: ts.isoformat())
        df_merged = df_merged.fillna(0)

        return df_merged.to_dict(orient="records")

    except Exception as e:
        print(f"Data pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/map-data")
def get_map_data(hours: int = 24):
    """
    Fetches the recent demand and price across all NEM regions to power the frontend geospatial map.
    Returns the full recent window (e.g., 24 hours) to support timeline slider interactions.
    """
    try:
        pricing_client = OpenNEMClient()
        df = pricing_client.get_latest_nem_demand(hours=hours)
        
        if df is not None and not df.empty:
            # Return requested window with sparse metrics forward-filled per region.
            df = df.sort_values(["network_region", "interval"]).copy()
            value_cols = [col for col in ("demand", "price") if col in df.columns]
            if value_cols:
                df[value_cols] = df.groupby("network_region")[value_cols].ffill()
                df = df.dropna(subset=value_cols, how="all")
            df = df.sort_values(["interval", "network_region"])
            return df.to_dict(orient="records")
            
        return []
    except Exception as e:
        print(f"Map data pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/victoria-data")
def get_victoria_data(hours: int = 24):
    """
    Returns VIC1 energy data and 5-region Victoria weather for the latest window.
    """
    try:
        pricing_client = OpenNEMClient()
        meteo_client = OpenMeteoClient()

        df_energy = pricing_client.get_market_timeseries(nem_region="VIC1", days=2)
        df_weather = meteo_client.get_multi_location_weather_df(
            locations=VICTORIA_WEATHER_LOCATIONS,
            hours=hours,
        )

        energy_records = []
        weather_records = []
        tz = "Australia/Melbourne"
        now_local = pd.Timestamp.now(tz=tz)
        cutoff = now_local - pd.Timedelta(hours=hours)

        if df_energy is not None and not df_energy.empty:
            normalized_energy = normalize_live_energy_df(df_energy.reset_index(), cfg=load_forecasting_config())
            normalized_energy = normalized_energy.sort_values("timestamp")
            normalized_energy = normalized_energy[
                (normalized_energy["timestamp"] > cutoff)
                & (normalized_energy["timestamp"] <= now_local)
            ]
            # OE responses can occasionally contain sparse demand/price points.
            # Carry forward last known values instead of forcing artificial zeros.
            normalized_energy[["demand", "spot_price"]] = normalized_energy[
                ["demand", "spot_price"]
            ].ffill()
            normalized_energy = normalized_energy.dropna(
                subset=["demand", "spot_price"],
                how="all",
            )
            normalized_energy = normalized_energy[["timestamp", "demand", "spot_price"]].rename(
                columns={"spot_price": "price"}
            )
            normalized_energy["timestamp"] = normalized_energy["timestamp"].apply(
                lambda ts: ts.isoformat()
            )
            energy_records = normalized_energy.to_dict(orient="records")

        if df_weather is not None and not df_weather.empty:
            weather_cols = [
                "timestamp",
                "region",
                "temperature",
                "solar_irradiance",
                "cloudcover",
                "wind_speed",
            ]
            normalized_weather = df_weather[weather_cols].sort_values(["timestamp", "region"])
            normalized_weather = normalized_weather.fillna(0)
            normalized_weather["timestamp"] = normalized_weather["timestamp"].apply(
                lambda ts: ts.isoformat()
            )
            weather_records = normalized_weather.to_dict(orient="records")

        return {
            "locations": VICTORIA_WEATHER_LOCATIONS,
            "energy": energy_records,
            "weather": weather_records,
        }
    except Exception as e:
        print(f"Victoria data pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))