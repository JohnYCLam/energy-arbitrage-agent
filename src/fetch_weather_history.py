from datetime import datetime, timedelta
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Load API Clients
from api_clients.open_meteo import OpenMeteoClient

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def load_settings():
    with open(BASE_DIR / "config" / "settings.yaml", "r") as f:
        return yaml.safe_load(f)

def fetch_weather_history(days_to_fetch=730):
    settings = load_settings()
    lat = settings["location"]["latitude"]
    lon = settings["location"]["longitude"]
    
    raw_dir = BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching {days_to_fetch} days of historical weather data...")
    meteo_client = OpenMeteoClient()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_to_fetch)
    
    df_weather = meteo_client.get_historical_weather_df(
        latitude=lat, longitude=lon,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d")
    )
    
    if df_weather is not None and not df_weather.empty:
        weather_path = raw_dir / f"weather_{lat}_{lon}_{days_to_fetch}d.csv"
        df_weather.to_csv(weather_path, index=False)
        print(f"✅ Saved {len(df_weather)} weather records to {weather_path.name}")

if __name__ == "__main__":
    fetch_weather_history(days_to_fetch=730)