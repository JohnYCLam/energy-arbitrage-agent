import requests
from datetime import date, timedelta
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
            "timezone": "auto" # Let Open-Meteo handle timezone conversion initially
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


if __name__ == "__main__":
    client = OpenMeteoClient()
    end_date = date.today()
    start_date = end_date - timedelta(days=2)

    latitude = -33.8688
    longitude = 151.2093

    print("--- Fetching Open-Meteo historical weather (last 2 days) ---")
    weather_data = client.get_historical_weather_payload(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    if not weather_data:
        print("No weather payload received.")
    else:
        print(f"Top-level keys: {list(weather_data.keys())}")
        hourly = weather_data.get("hourly", {})
        if hourly:
            hourly_fields = list(hourly.keys())
            print(f"Hourly fields: {hourly_fields}")
            record_count = len(hourly.get("time", []))
            print(f"Hourly record count: {record_count}")

            sample_df = pd.DataFrame(hourly).head(5)
            if not sample_df.empty:
                print("\nSample hourly rows:")
                print(sample_df.to_string(index=False))
        else:
            print("Payload missing 'hourly' data.")

    df_weather = client._hourly_payload_to_df(weather_data)
    if df_weather is None or df_weather.empty:
        print("\nDataFrame helper returned no data.")
    else:
        print("\nStandardized DataFrame preview:")
        print(df_weather.head(5).to_string(index=False))
        print(f"DataFrame shape: {df_weather.shape}")