import requests
from typing import Dict, Any, List, Optional, Union
import pandas as pd

class OpenMeteoClient:
    """
    A client for fetching historical weather data from the Open-Meteo API.
    """
    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

    @staticmethod
    def _hourly_payload_to_df(weather_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Converts an Open-Meteo payload to a standardized weather DataFrame.
        """
        if not weather_data or "hourly" not in weather_data:
            return None

        df_weather = pd.DataFrame(weather_data["hourly"])
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

    def get_historical_weather_payload(
        self,
        latitude: Union[float, List[float]],
        longitude: Union[float, List[float]],
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
        """
        Fetches historical weather data for a given location (or multiple locations) and date range.
        Supports lists of coordinates for geospatial grid visualization.

        Args:
            latitude: The latitude(s) of the location.
            longitude: The longitude(s) of the location.
            start_date: The start date in 'YYYY-MM-DD' format.
            end_date: The end date in 'YYYY-MM-DD' format.

        Returns:
            A dictionary containing the API response.
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
        cutoff = now_local - pd.Timedelta(hours=hours)
        df = df[(df["timestamp"] > cutoff) & (df["timestamp"] <= now_local)]
        return df.sort_values("timestamp").reset_index(drop=True)


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