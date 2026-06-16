import requests
from typing import Dict, Any, List, Optional, Union, Sequence
import pandas as pd

class OpenMeteoClient:
    """
    A client for fetching historical weather data from the Open-Meteo API.
    """
    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

    @staticmethod
    def _normalize_hourly_df(df_weather: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Normalizes Open-Meteo hourly columns to a consistent schema."""
        if df_weather.empty:
            return None

        df_weather = df_weather.rename(
            columns={
                "time": "timestamp",
                "shortwave_radiation": "solar_irradiance",
                "temperature_2m": "temperature",
                "wind_speed_10m": "wind_speed",
            }
        )
        return df_weather

    @classmethod
    def _hourly_payload_to_df(cls, weather_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Converts a single-location Open-Meteo payload to a standardized DataFrame.
        """
        if not weather_data or "hourly" not in weather_data:
            return None

        df_weather = pd.DataFrame(weather_data["hourly"])
        return cls._normalize_hourly_df(df_weather)

    @classmethod
    def _multi_location_payload_to_df(
        cls,
        weather_data: Sequence[Dict[str, Any]],
        location_names: Sequence[str],
    ) -> Optional[pd.DataFrame]:
        """
        Converts a multi-location Open-Meteo payload to a tidy DataFrame.

        Open-Meteo returns a JSON array (one payload per coordinate pair) when
        latitude/longitude are provided as comma-separated lists.
        """
        if not weather_data:
            return None

        frames: List[pd.DataFrame] = []
        for idx, payload in enumerate(weather_data):
            if "hourly" not in payload:
                continue
            hourly_df = pd.DataFrame(payload["hourly"])
            hourly_df = cls._normalize_hourly_df(hourly_df)
            if hourly_df is None or hourly_df.empty:
                continue
            location_name = location_names[idx] if idx < len(location_names) else f"loc_{idx}"
            hourly_df["region"] = location_name
            frames.append(hourly_df)

        if not frames:
            return None
        return pd.concat(frames, ignore_index=True)

    def get_historical_weather_payload(
        self,
        latitude: Union[float, List[float]],
        longitude: Union[float, List[float]],
        start_date: str,
        end_date: str,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Fetches historical weather data and returns the raw API JSON payload.
        """
        return self.get_historical_weather(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )

    def get_historical_weather(
        self,
        latitude: Union[float, List[float]],
        longitude: Union[float, List[float]],
        start_date: str,
        end_date: str,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Fetches historical weather data for a given location (or multiple locations) and date range.
        Supports lists of coordinates for geospatial grid visualization.

        Args:
            latitude: The latitude(s) of the location.
            longitude: The longitude(s) of the location.
            start_date: The start date in 'YYYY-MM-DD' format.
            end_date: The end date in 'YYYY-MM-DD' format.

        Returns:
            API response payload. Single-location requests return one dictionary.
            Multi-location requests return a list of dictionaries.
        """
        lat_param = ",".join(map(str, latitude)) if isinstance(latitude, list) else latitude
        lon_param = ",".join(map(str, longitude)) if isinstance(longitude, list) else longitude

        params = {
            "latitude": lat_param,
            "longitude": lon_param,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,shortwave_radiation,cloudcover,wind_speed_10m",
            "timezone": "Australia/Melbourne"  # Match the AEST(+10:00) energy timestamps
        }
        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while fetching weather data: {e}")
            return {}

    @staticmethod
    def _clip_latest_hours(
        df: pd.DataFrame,
        *,
        hours: int,
        timezone: str,
    ) -> pd.DataFrame:
        """Clips weather data to the trailing time window ending at now."""
        now_local = pd.Timestamp.now(tz=timezone)
        cutoff = now_local - pd.Timedelta(hours=hours)
        clipped = df[(df["timestamp"] > cutoff) & (df["timestamp"] <= now_local)]
        return clipped.sort_values("timestamp").reset_index(drop=True)

    def get_historical_weather_df(
        self,
        latitude: Union[float, List[float]],
        longitude: Union[float, List[float]],
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetches historical weather data and returns a standardized pandas DataFrame.

        Returns:
            A DataFrame with normalized weather columns, or None if no hourly data is available.
        """
        weather_data = self.get_historical_weather_payload(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )
        if isinstance(weather_data, list):
            return None
        return self._hourly_payload_to_df(weather_data)

    def get_latest_weather_df(
        self,
        latitude: Union[float, List[float]],
        longitude: Union[float, List[float]],
        hours: int = 24,
    ) -> Optional[pd.DataFrame]:
        """
        Returns only the most recent `hours` of weather in Melbourne local time
        (tz-aware, +10:00) to match the AEST energy timestamps.

        The Open-Meteo archive API returns whole calendar days, padding the
        current day with future-dated rows. This clips to the trailing window
        ending at "now" so the data never extends into the future.
        """
        tz = "Australia/Melbourne"
        now_local = pd.Timestamp.now(tz=tz)
        # Fetch an extra day of buffer so a full window survives the clip,
        # regardless of timezone offsets or archive lag at the edges.
        start_date = (now_local - pd.Timedelta(hours=hours) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = now_local.strftime("%Y-%m-%d")

        df = self.get_historical_weather_df(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )
        if df is None or df.empty:
            return None

        # Open-Meteo returns naive local strings; localize them to Melbourne.
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(tz)
        return self._clip_latest_hours(df, hours=hours, timezone=tz)

    def get_multi_location_weather_df(
        self,
        locations: Sequence[Dict[str, Any]],
        hours: int = 24,
    ) -> Optional[pd.DataFrame]:
        """
        Fetches latest weather for multiple locations in one batched API call.

        Returns tidy rows with columns:
        timestamp, region, temperature, solar_irradiance, cloudcover, wind_speed
        """
        if not locations:
            return None

        tz = "Australia/Melbourne"
        now_local = pd.Timestamp.now(tz=tz)
        start_date = (now_local - pd.Timedelta(hours=hours) - pd.Timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        end_date = now_local.strftime("%Y-%m-%d")

        latitudes = [float(location["latitude"]) for location in locations]
        longitudes = [float(location["longitude"]) for location in locations]
        names = [str(location["name"]) for location in locations]

        payload = self.get_historical_weather_payload(
            latitude=latitudes,
            longitude=longitudes,
            start_date=start_date,
            end_date=end_date,
        )

        if not isinstance(payload, list):
            return None

        df = self._multi_location_payload_to_df(payload, names)
        if df is None or df.empty:
            return None

        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(
            tz,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
        return self._clip_latest_hours(df, hours=hours, timezone=tz)


if __name__ == "__main__":
    client = OpenMeteoClient()

    latitude = -37.8136   # Melbourne
    longitude = 144.9631

    print("--- Fetching Open-Meteo weather (latest 24 hours, Melbourne time) ---")
    df_weather = client.get_latest_weather_df(latitude, longitude, hours=24)

    if df_weather is None or df_weather.empty:
        print("No weather data received.")
    else:
        print(f"Records: {len(df_weather)} | Columns: {list(df_weather.columns)}")
        print("\nHead:")
        print(df_weather.head().to_string(index=False))
        print("\nTail:")
        print(df_weather.tail().to_string(index=False))