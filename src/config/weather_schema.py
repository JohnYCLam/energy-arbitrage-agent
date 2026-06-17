"""Shared weather export schema and normalization helpers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from config.locations import VICTORIA_WEATHER_LOCATIONS

TZ = "Australia/Melbourne"

# Approximate start of Previous Runs archive for most Open-Meteo models.
FORECAST_HISTORY_MIN_DATE = pd.Timestamp("2024-01-01")

WEATHER_FEATURE_COLUMNS = [
    "temperature",
    "solar_irradiance",
    "cloudcover",
    "wind_speed",
]

WEATHER_EXPORT_COLUMNS = [
    "region",
    "timestamp",
    "forecast_issue_time",
    "lead_hours",
    "latitude",
    "longitude",
    "record_type",
    "source",
    *WEATHER_FEATURE_COLUMNS,
]

ACTUAL_DEDUPE_COLUMNS = ["region", "timestamp"]
FORECAST_DEDUPE_COLUMNS = ["region", "forecast_issue_time", "timestamp", "lead_hours"]


def build_date_chunks(days_to_fetch: int, chunk_days: int) -> List[Dict[str, date]]:
    if days_to_fetch <= 0:
        raise ValueError("days_to_fetch must be greater than 0.")
    if chunk_days <= 0:
        raise ValueError("chunk_days must be greater than 0.")

    end_date = pd.Timestamp.now(tz=TZ).date()
    start_date = end_date - timedelta(days=days_to_fetch)
    chunks: List[Dict[str, date]] = []

    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_date)
        chunks.append({"start": cursor, "end": chunk_end})
        cursor = chunk_end + timedelta(days=1)

    return chunks


def resolve_fetch_locations(
    *,
    all_vic_regions: bool,
    region_names: Optional[Sequence[str]],
    settings: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if all_vic_regions:
        return list(VICTORIA_WEATHER_LOCATIONS)

    if region_names:
        requested = {name.strip() for name in region_names if name.strip()}
        selected = [loc for loc in VICTORIA_WEATHER_LOCATIONS if loc["name"] in requested]
        if not selected:
            raise ValueError(f"No matching VIC regions found for: {sorted(requested)}")
        return selected

    return [
        {
            "name": "site",
            "latitude": float(settings["location"]["latitude"]),
            "longitude": float(settings["location"]["longitude"]),
        }
    ]


def finalize_actual_weather_df(
    df: pd.DataFrame,
    *,
    region: str,
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    work = df.copy()
    if "timestamp" not in work.columns and "time" in work.columns:
        work = work.rename(columns={"time": "timestamp"})

    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp"])
    work["region"] = region
    work["forecast_issue_time"] = pd.NaT
    work["lead_hours"] = 0
    work["latitude"] = latitude
    work["longitude"] = longitude
    work["record_type"] = "actual"
    work["source"] = "open_meteo_archive"

    for column in WEATHER_FEATURE_COLUMNS:
        if column not in work.columns:
            work[column] = pd.NA

    return work[WEATHER_EXPORT_COLUMNS].sort_values(["region", "timestamp"]).reset_index(drop=True)


def finalize_forecast_weather_df(
    df: pd.DataFrame,
    *,
    region: str,
    latitude: float,
    longitude: float,
    source: str,
) -> pd.DataFrame:
    work = df.copy()
    if "timestamp" not in work.columns and "target_time" in work.columns:
        work = work.rename(columns={"target_time": "timestamp"})

    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work["forecast_issue_time"] = pd.to_datetime(work["forecast_issue_time"], errors="coerce")
    work = work.dropna(subset=["timestamp", "forecast_issue_time"])
    work["region"] = region
    work["latitude"] = latitude
    work["longitude"] = longitude
    work["record_type"] = "forecast"
    work["source"] = source

    for column in WEATHER_FEATURE_COLUMNS:
        if column not in work.columns:
            work[column] = pd.NA

    return work[WEATHER_EXPORT_COLUMNS].sort_values(
        ["region", "forecast_issue_time", "timestamp"]
    ).reset_index(drop=True)


def clip_actual_to_trailing_window(df: pd.DataFrame, *, days_to_fetch: int) -> pd.DataFrame:
    if df.empty:
        return df

    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp"]).sort_values(["region", "timestamp"])
    work["timestamp"] = work["timestamp"].dt.tz_localize(
        TZ,
        ambiguous="NaT",
        nonexistent="shift_forward",
    )

    now_local = pd.Timestamp.now(tz=TZ)
    start_bound = now_local - pd.Timedelta(days=days_to_fetch)
    clipped = work[(work["timestamp"] > start_bound) & (work["timestamp"] <= now_local)].copy()
    clipped["timestamp"] = clipped["timestamp"].dt.tz_localize(None)
    clipped["forecast_issue_time"] = pd.NaT
    return clipped.reset_index(drop=True)


def clip_forecast_to_trailing_window(df: pd.DataFrame, *, days_to_fetch: int) -> pd.DataFrame:
    if df.empty:
        return df

    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work["forecast_issue_time"] = pd.to_datetime(work["forecast_issue_time"], errors="coerce")
    work = work.dropna(subset=["timestamp", "forecast_issue_time"]).sort_values(
        ["region", "timestamp", "forecast_issue_time"]
    )
    work["timestamp"] = work["timestamp"].dt.tz_localize(
        TZ,
        ambiguous="NaT",
        nonexistent="shift_forward",
    )
    work["forecast_issue_time"] = work["forecast_issue_time"].dt.tz_localize(
        TZ,
        ambiguous="NaT",
        nonexistent="shift_forward",
    )

    now_local = pd.Timestamp.now(tz=TZ)
    start_bound = now_local - pd.Timedelta(days=days_to_fetch)
    clipped = work[
        (work["timestamp"] > start_bound)
        & (work["timestamp"] <= now_local)
        & (work["forecast_issue_time"] <= work["timestamp"])
    ].copy()
    clipped["timestamp"] = clipped["timestamp"].dt.tz_localize(None)
    clipped["forecast_issue_time"] = clipped["forecast_issue_time"].dt.tz_localize(None)
    return clipped.reset_index(drop=True)


def validate_actual_weather_df(
    df: pd.DataFrame,
    *,
    region: str,
    expected_start: pd.Timestamp,
    expected_end: pd.Timestamp,
    interval_minutes: int = 60,
) -> None:
    if df.empty:
        raise ValueError(f"[{region}] Validation failed: dataframe is empty.")

    work = df[df["region"] == region].copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp"]).sort_values("timestamp")
    min_ts = work["timestamp"].min()
    max_ts = work["timestamp"].max()
    duplicates = int(work.duplicated(subset=ACTUAL_DEDUPE_COLUMNS).sum())

    print(f"[{region}] Actual validation:")
    print(f"  Coverage: {min_ts} -> {max_ts}")
    print(f"  Rows: {len(work)} | Duplicates: {duplicates}")

    if min_ts > expected_start + pd.Timedelta(hours=2):
        raise ValueError(f"[{region}] Validation failed: data starts too late ({min_ts}).")
    if max_ts < expected_end - pd.Timedelta(hours=2):
        raise ValueError(f"[{region}] Validation failed: data ends too early ({max_ts}).")


def validate_forecast_weather_df(
    df: pd.DataFrame,
    *,
    region: str,
    expected_start: pd.Timestamp,
    expected_end: pd.Timestamp,
    allow_partial_start: bool = True,
) -> None:
    if df.empty:
        raise ValueError(f"[{region}] Validation failed: dataframe is empty.")

    work = df[df["region"] == region].copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work["forecast_issue_time"] = pd.to_datetime(work["forecast_issue_time"], errors="coerce")
    work = work.dropna(subset=["timestamp", "forecast_issue_time"]).sort_values("timestamp")
    min_ts = work["timestamp"].min()
    max_ts = work["timestamp"].max()
    duplicates = int(work.duplicated(subset=FORECAST_DEDUPE_COLUMNS).sum())
    invalid_lead = int((work["forecast_issue_time"] > work["timestamp"]).sum())

    print(f"[{region}] Forecast validation:")
    print(f"  Target coverage: {min_ts} -> {max_ts}")
    print(f"  Rows: {len(work)} | Duplicates: {duplicates}")
    if allow_partial_start and min_ts > expected_start + pd.Timedelta(days=1):
        print(
            f"  Note: partial forecast-history start ({min_ts}) is expected "
            f"(Previous Runs archive begins around {FORECAST_HISTORY_MIN_DATE.date()})."
        )

    if invalid_lead > 0:
        raise ValueError(f"[{region}] Validation failed: forecast_issue_time must be <= timestamp.")
    if not allow_partial_start and min_ts > expected_start + pd.Timedelta(hours=2):
        raise ValueError(f"[{region}] Validation failed: data starts too late ({min_ts}).")
    if max_ts < expected_end - pd.Timedelta(hours=2):
        raise ValueError(f"[{region}] Validation failed: data ends too early ({max_ts}).")
