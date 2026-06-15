import pandas as pd
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Load API Clients
from api_clients.pricing_api import OpenNEMClient

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def load_settings():
    with open(BASE_DIR / "config" / "settings.yaml", "r") as f:
        return yaml.safe_load(f)

def fetch_energy_history(days_to_fetch=730):
    settings = load_settings()
    primary_region = settings["market"]["nem_region"]
    adjacent_regions = settings["market"].get("adjacent_regions", [])
    all_regions = [primary_region] + adjacent_regions
    
    # Ensure output directory exists
    raw_dir = BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    pricing_client = OpenNEMClient()
    
    for region in all_regions:
        print(f"\nFetching {days_to_fetch} days of historical market data for {region}...")
        df_merged = pricing_client.get_regional_energy_data(nem_region=region, days=days_to_fetch)
            
        if df_merged is not None and not df_merged.empty:
            market_path = raw_dir / f"market_{region}_{days_to_fetch}d.csv"
            df_merged.to_csv(market_path, index=False)
            print(f"✅ Saved {len(df_merged)} market records to {market_path.name}")

if __name__ == "__main__":
    fetch_energy_history(days_to_fetch=730)