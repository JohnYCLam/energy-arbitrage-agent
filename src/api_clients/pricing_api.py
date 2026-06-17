import pandas as pd
from typing import Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_env_fallback(env_path: Path) -> None:
    """Minimal .env loader for local script usage."""
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

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
        # Ensure .env is loaded when this module is run directly.
        project_root = Path(__file__).resolve().parents[2]
        if load_dotenv is not None:
            load_dotenv(project_root / ".env")
        else:
            _load_env_fallback(project_root / ".env")
        self.client = OEClient()

    @staticmethod
    def _to_naive_melbourne(dt: datetime) -> datetime:
        """
        Normalizes datetimes for OpenElectricity API calls.

        The OpenElectricity SDK may reject tz-aware datetimes in some environments,
        and older working code uses naive `datetime.now()` interpreted in local
        exchange time (AEST/AEDT).

        So for tz-aware datetimes, convert to Australia/Melbourne and drop tzinfo.
        """
        if dt.tzinfo is None:
            # Treat naive as already in exchange/local time to preserve previous behavior.
            return dt
        mel_ts = pd.Timestamp(dt).tz_convert("Australia/Melbourne")
        return mel_ts.to_pydatetime().replace(tzinfo=None)

    def _get_interconnector_flow_timeseries(
        self,
        *,
        client,
        nem_region: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        """
        Fetches interconnector imports/exports and derives net flow (MW).

        Convention: positive values indicate net imports into the region,
        negative values indicate net exports.
        """
        flow_imports_metric = getattr(MarketMetric, "FLOW_IMPORTS", None)
        flow_exports_metric = getattr(MarketMetric, "FLOW_EXPORTS", None)
        if flow_imports_metric is None or flow_exports_metric is None:
            return None

        start_date_api = self._to_naive_melbourne(start_date)
        end_date_api = self._to_naive_melbourne(end_date)
        flow_response = client.get_market(
            network_code="NEM",
            network_region=nem_region,
            metrics=[flow_imports_metric, flow_exports_metric],
            interval="5m",
            date_start=start_date_api,
            date_end=end_date_api,
        )

        extracted_flow = []
        for timeseries in flow_response.data:
            metric_name = (
                timeseries.metric.value
                if hasattr(timeseries.metric, "value")
                else str(timeseries.metric)
            )
            for result in timeseries.results:
                for data_point in result.data:
                    extracted_flow.append(
                        {
                            "interval": data_point.timestamp,
                            "metric": str(metric_name).lower(),
                            "value": data_point.value,
                        }
                    )

        if not extracted_flow:
            return None

        flow_df = pd.DataFrame(extracted_flow)
        flow_pivot = (
            flow_df.pivot_table(index="interval", columns="metric", values="value")
            .reset_index()
            .fillna(0)
        )
        flow_pivot.columns.name = None

        imports_col = "flow_imports"
        exports_col = "flow_exports"
        if imports_col not in flow_pivot.columns:
            flow_pivot[imports_col] = 0.0
        if exports_col not in flow_pivot.columns:
            flow_pivot[exports_col] = 0.0

        flow_pivot["interconnector_flow_mw"] = (
            flow_pivot[imports_col] - flow_pivot[exports_col]
        )
        return flow_pivot[["interval", "interconnector_flow_mw"]]

    def get_market_timeseries_range(
        self,
        nem_region: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        try:
            with self.client as client:
                start_date_api = self._to_naive_melbourne(start_date)
                end_date_api = self._to_naive_melbourne(end_date)
                res = client.get_market(
                    network_code="NEM",
                    network_region=nem_region,
                    metrics=[MarketMetric.PRICE, MarketMetric.DEMAND],
                    interval="5m",
                    date_start=start_date_api,
                    date_end=end_date_api,
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

    def get_market_timeseries(self, nem_region: str, days: int = 1) -> Optional[pd.DataFrame]:
        # Using AEST local time correctly
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_market_timeseries_range(nem_region, start_date, end_date)

    def get_network_timeseries_range(
        self,
        nem_region: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        class MetricMock:
            def __init__(self, val): self.value = val
                
        power_metric = getattr(NetworkMetric, "POWER", MetricMock("power"))

        try:
            with self.client as client:
                start_date_api = self._to_naive_melbourne(start_date)
                end_date_api = self._to_naive_melbourne(end_date)
                res = client.get_network_data(
                    network_code="NEM",
                    network_region=nem_region,
                    metrics=[power_metric],
                    interval="5m",
                    date_start=start_date_api,
                    date_end=end_date_api,
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

                # Fetch real interconnector imports/exports and derive net MW flow.
                # If unavailable, keep schema stable with zeros.
                flow_df = self._get_interconnector_flow_timeseries(
                    client=client,
                    nem_region=nem_region,
                    start_date=start_date,
                    end_date=end_date,
                )
                if flow_df is not None and not flow_df.empty:
                    df_final = pd.merge(df_final, flow_df, on="interval", how="left")
                    df_final["interconnector_flow_mw"] = df_final[
                        "interconnector_flow_mw"
                    ].fillna(0.0)
                else:
                    df_final["interconnector_flow_mw"] = 0.0
                
                return df_final.sort_values("interval").reset_index(drop=True)
                
        except Exception as e:
            print(f"An error occurred while fetching network timeseries: {e}")
            return None

    def get_network_timeseries(self, nem_region: str, days: int = 1) -> Optional[pd.DataFrame]:
        # Using AEST local time correctly
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_network_timeseries_range(nem_region, start_date, end_date)

    def get_regional_energy_data_range(
        self,
        nem_region: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        df_market = self.get_market_timeseries_range(nem_region, start_date, end_date)
        df_network = self.get_network_timeseries_range(nem_region, start_date, end_date)

        df_merged = df_market
        if df_merged is not None and df_network is not None and not df_network.empty:
            df_merged = pd.merge(df_merged, df_network, on="interval", how="outer").sort_values("interval").reset_index(drop=True)
        elif df_merged is None and df_network is not None:
            df_merged = df_network
            
        return df_merged

    def get_regional_energy_data(self, nem_region: str, days: int = 1) -> Optional[pd.DataFrame]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_regional_energy_data_range(nem_region, start_date, end_date)

    def get_latest_nem_demand(self, regions: Optional[list] = None, hours: int = 2) -> Optional[pd.DataFrame]:
        regions = regions or self.DEFAULT_NEM_REGIONS
        start_date = datetime.now() - timedelta(hours=hours)
        
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