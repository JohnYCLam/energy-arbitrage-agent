import pandas as pd
from typing import Optional
from datetime import datetime, timedelta

try:
    from openelectricity import OEClient
    from openelectricity.types import MarketMetric
    try:
        from openelectricity.types import NetworkMetric
    except ImportError:
        NetworkMetric = None
except ImportError:
    raise ImportError("Please install the OpenElectricity SDK: pip install 'openelectricity[analysis]'")

class OpenNEMClient:
    """
    A client for fetching historical electricity market data using the official OpenElectricity Python SDK.
    """
    DEFAULT_NEM_REGIONS = ["VIC1", "NSW1", "QLD1", "SA1", "TAS1"]

    def __init__(self):
        self.client = OEClient()

    def get_market_timeseries(self, nem_region: str, days: int = 1) -> Optional[pd.DataFrame]:
        # Using AEST local time correctly
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            with self.client as client:
                res = client.get_market(
                    network_code="NEM",
                    network_region=nem_region,
                    metrics=[MarketMetric.PRICE, MarketMetric.DEMAND],
                    interval="5m",
                    date_start=start_date,
                    date_end=end_date,
                )
                
                # Manual JSON Parse bypassing .to_pandas()
                extracted_data = []
                for timeseries in res.data:
                    for result in timeseries.results:
                        metric_name = timeseries.metric.value if hasattr(timeseries.metric, 'value') else str(timeseries.metric)
                        for data_point in result.data:
                            extracted_data.append({
                                "interval": data_point.timestamp,
                                "metric": metric_name,
                                "value": data_point.value
                            })
                            
                if not extracted_data:
                    return None
                    
                df_flat = pd.DataFrame(extracted_data)
                df_pivot = df_flat.pivot_table(
                    index="interval",
                    columns="metric",
                    values="value"
                ).reset_index()
                
                df_pivot.columns.name = None
                return df_pivot.sort_values("interval").reset_index(drop=True)
                
        except Exception as e:
            print(f"An error occurred while fetching market timeseries: {e}")
            return None
            
    def get_network_timeseries(self, nem_region: str, days: int = 1) -> Optional[pd.DataFrame]:
        # Using AEST local time correctly
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        class MetricMock:
            def __init__(self, val): self.value = val
                
        power_metric = getattr(NetworkMetric, "POWER", MetricMock("power"))

        try:
            with self.client as client:
                res = client.get_network_data(
                    network_code="NEM",
                    network_region=nem_region,
                    metrics=[power_metric],
                    interval="5m",
                    date_start=start_date,
                    date_end=end_date,
                    secondary_grouping="fueltech_group"
                )
                
                # Manual JSON Parse bypassing .to_pandas()
                extracted_data = []
                for timeseries in res.data:
                    if not timeseries.results:
                        continue
                    for result in timeseries.results:
                        parts = result.name.split("_")
                        fueltech = "_".join(parts[2:]) if len(parts) > 2 else result.name
                        for data_point in result.data:
                            extracted_data.append({
                                "interval": data_point.timestamp,
                                "fueltech": fueltech,
                                "power": data_point.value
                            })
                            
                if not extracted_data:
                    return None
                    
                df_flat = pd.DataFrame(extracted_data)
                df_pivot = df_flat.pivot_table(
                    index="interval", 
                    columns="fueltech", 
                    values="power", 
                    aggfunc="sum"
                ).fillna(0).reset_index()
                
                renew_cols = [c for c in df_pivot.columns if any(x in c.lower() for x in ["solar", "wind", "hydro"])]
                df_pivot["renewable_generation"] = df_pivot[renew_cols].sum(axis=1) if renew_cols else 0.0
                
                rename_map = {c: f"gen_{c.lower()}" for c in df_pivot.columns if c not in ["interval", "renewable_generation"]}
                df_final = df_pivot.rename(columns=rename_map)
                df_final.columns.name = None
                
                # Maintain downstream schema consistency
                df_final["interconnector_flow_mw"] = 0.0
                
                return df_final.sort_values("interval").reset_index(drop=True)
                
        except Exception as e:
            print(f"An error occurred while fetching network timeseries: {e}")
            return None
            
    def get_regional_energy_data(self, nem_region: str, days: int = 1) -> Optional[pd.DataFrame]:
        df_market = self.get_market_timeseries(nem_region, days)
        df_network = self.get_network_timeseries(nem_region, days)

        df_merged = df_market
        if df_merged is not None and df_network is not None and not df_network.empty:
            df_merged = pd.merge(df_merged, df_network, on="interval", how="outer").sort_values("interval").reset_index(drop=True)
        elif df_merged is None and df_network is not None:
            df_merged = df_network
            
        return df_merged

    def get_latest_nem_demand(self, regions: Optional[list] = None) -> Optional[pd.DataFrame]:
        regions = regions or self.DEFAULT_NEM_REGIONS
        start_date = datetime.now() - timedelta(hours=2)
        
        try:
            with self.client as client:
                res = client.get_market(
                    network_code="NEM",
                    metrics=[MarketMetric.PRICE, MarketMetric.DEMAND],
                    interval="5m",
                    date_start=start_date,
                    primary_grouping="network_region" 
                )
                
                extracted_data = []
                for timeseries in res.data:
                    for result in timeseries.results:
                        region = result.name.split("_")[-1] if "_" in result.name else result.name
                        if region not in regions:
                            continue
                        metric_name = timeseries.metric.value if hasattr(timeseries.metric, 'value') else str(timeseries.metric)
                        for data_point in result.data:
                            extracted_data.append({
                                "interval": data_point.timestamp,
                                "network_region": region,
                                "metric": metric_name,
                                "value": data_point.value
                            })
                            
                if not extracted_data:
                    return None
                    
                df_flat = pd.DataFrame(extracted_data)
                df_pivot = df_flat.pivot_table(
                    index=["interval", "network_region"], 
                    columns="metric", 
                    values="value"
                ).reset_index()
                
                df_pivot.columns.name = None
                return df_pivot.sort_values(["interval", "network_region"]).reset_index(drop=True)
                
        except Exception as e:
            print(f"An error occurred while fetching latest demand: {e}")
            return None

if __name__ == "__main__":
    client = OpenNEMClient()
    print("--- Fetching market & network timeseries for VIC1 (last 1 day) ---")
    df_merged = client.get_regional_energy_data("VIC1", days=1)
    if df_merged is not None:
        print(df_merged.head(10))
        print(f"Shape: {df_merged.shape}")
        print(df_merged.tail(10))
        
    print("\n--- Fetching latest NEM demand across all regions ---")
    demand_df = client.get_latest_nem_demand()
    if demand_df is not None:
        print(demand_df.head(10))
        print(f"Shape: {demand_df.shape}")