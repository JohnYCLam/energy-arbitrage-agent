from pathlib import Path
from typing import Dict, List
import argparse
import sys

import pandas as pd
import yaml
from dotenv import load_dotenv

from api_clients.open_meteo import OpenMeteoClient
from config.weather_schema import (
    FORECAST_DEDUPE_COLUMNS,
    WEATHER_EXPORT_COLUMNS,
    build_date_chunks,
    clip_forecast_to_trailing_window,
    finalize_forecast_weather_df,
    resolve_fetch_locations,
    validate_forecast_weather_df,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
TZ = "Australia/Melbourne"


def load_settings():
    with open(BASE_DIR / "config" / "settings.yaml", "r") as f:
        return yaml.safe_load(f)


def _fetch_forecast_history_for_location(
    *,
    location: Dict,
    days_to_fetch: int,
    chunk_days: int,
    lead_days: int,
    meteo_client: OpenMeteoClient,
    chunks: List[Dict],
) -> pd.DataFrame:
    region = str(location["name"])
    lat = float(location["latitude"])
    lon = float(location["longitude"])
    frames: List[pd.DataFrame] = []

    print(
        f"\n[{region}] Fetching {days_to_fetch} days of forecast history at ({lat}, {lon}) "
        f"(lead_days={lead_days}) in {len(chunks)} chunks ({chunk_days} days each)..."
    )

    for idx, chunk in enumerate(chunks, start=1):
        start_str = chunk["start"].strftime("%Y-%m-%d")
        end_str = chunk["end"].strftime("%Y-%m-%d")
        print(f"  [{idx}/{len(chunks)}] {start_str} -> {end_str}")

        df_chunk = meteo_client.get_historical_forecast_df(
            latitude=lat,
            longitude=lon,
            start_date=start_str,
            end_date=end_str,
            lead_days=lead_days,
            timezone=TZ,
        )
        if df_chunk is None or df_chunk.empty:
            print("    ⚠️ Chunk returned no data.")
            continue

        frames.append(
            finalize_forecast_weather_df(
                df_chunk,
                region=region,
                latitude=lat,
                longitude=lon,
                source="previous_runs",
            )
        )
        print(f"    ✅ Rows fetched: {len(df_chunk)}")

    if not frames:
        return pd.DataFrame(columns=WEATHER_EXPORT_COLUMNS)

    df_region = pd.concat(frames, ignore_index=True)
    df_region = df_region.drop_duplicates(subset=FORECAST_DEDUPE_COLUMNS, keep="last")
    df_region = clip_forecast_to_trailing_window(df_region, days_to_fetch=days_to_fetch)
    return df_region.reset_index(drop=True)


def fetch_historical_forecast_history(
    *,
    days_to_fetch: int,
    chunk_days: int,
    lead_days: int,
    locations: List[Dict],
    fail_on_validation: bool,
) -> int:
    raw_dir = BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    meteo_client = OpenMeteoClient()
    chunks = build_date_chunks(days_to_fetch=days_to_fetch, chunk_days=chunk_days)
    if not chunks:
        raise ValueError("No chunks were generated; check days_to_fetch and chunk_days.")

    now_local = pd.Timestamp.now(tz=TZ)
    window_start = now_local - pd.Timedelta(days=days_to_fetch)
    expected_start = pd.Timestamp(window_start.strftime("%Y-%m-%d %H:%M:%S"))
    expected_end = pd.Timestamp(now_local.strftime("%Y-%m-%d %H:%M:%S"))

    region_frames: List[pd.DataFrame] = []
    overall_success = True

    for location in locations:
        df_region = _fetch_forecast_history_for_location(
            location=location,
            days_to_fetch=days_to_fetch,
            chunk_days=chunk_days,
            lead_days=lead_days,
            meteo_client=meteo_client,
            chunks=chunks,
        )
        if df_region.empty:
            print(f"❌ [{location['name']}] No forecast history fetched.")
            overall_success = False
            continue

        try:
            validate_forecast_weather_df(
                df_region,
                region=str(location["name"]),
                expected_start=expected_start,
                expected_end=expected_end,
                allow_partial_start=True,
            )
        except Exception as exc:
            print(f"❌ [{location['name']}] Validation error: {exc}")
            overall_success = False
            if fail_on_validation:
                continue

        region_frames.append(df_region)

    if not region_frames:
        return 1 if fail_on_validation else 0

    df_forecast = pd.concat(region_frames, ignore_index=True)
    df_forecast = df_forecast.drop_duplicates(subset=FORECAST_DEDUPE_COLUMNS, keep="last")
    df_forecast = df_forecast.sort_values(
        ["region", "forecast_issue_time", "timestamp"]
    ).reset_index(drop=True)

    print(
        f"\nClipped trailing window (Melbourne): "
        f"{window_start.strftime('%Y-%m-%d %H:%M')} -> {now_local.strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"Regions saved: {sorted(df_forecast['region'].unique())}")

    multi_region = len(locations) > 1
    if multi_region:
        output_name = f"weather_forecast_history_vic_{days_to_fetch}d_lead{lead_days}d.csv"
    else:
        output_name = (
            f"weather_forecast_history_{locations[0]['name'].lower()}_"
            f"{days_to_fetch}d_lead{lead_days}d.csv"
        )

    output_path = raw_dir / output_name
    df_forecast.to_csv(output_path, index=False)
    print(f"✅ Saved {len(df_forecast)} validated forecast-history rows to {output_path.name}")

    if not overall_success and fail_on_validation:
        return 1
    return 0


def fetch_live_forecast_snapshot(
    *,
    locations: List[Dict],
    forecast_hours: int,
    fail_on_validation: bool,
) -> int:
    raw_dir = BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    meteo_client = OpenMeteoClient()
    snapshot_frames: List[pd.DataFrame] = []

    for location in locations:
        region = str(location["name"])
        lat = float(location["latitude"])
        lon = float(location["longitude"])
        df_snapshot = meteo_client.get_live_forecast_snapshot_df(
            latitude=lat,
            longitude=lon,
            forecast_hours=forecast_hours,
            timezone=TZ,
        )
        if df_snapshot is None or df_snapshot.empty:
            print(f"❌ [{region}] Live forecast snapshot returned no data.")
            if fail_on_validation:
                continue
            continue

        snapshot_frames.append(
            finalize_forecast_weather_df(
                df_snapshot,
                region=region,
                latitude=lat,
                longitude=lon,
                source="live_forecast",
            )
        )
        print(f"✅ [{region}] Captured {len(df_snapshot)} live forecast rows.")

    if not snapshot_frames:
        return 1 if fail_on_validation else 0

    df_new = pd.concat(snapshot_frames, ignore_index=True)
    output_name = (
        "weather_forecast_snapshots_vic.csv"
        if len(locations) > 1
        else f"weather_forecast_snapshots_{locations[0]['name'].lower()}.csv"
    )
    output_path = raw_dir / output_name

    if output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, df_new], ignore_index=True)
    else:
        combined = df_new

    combined["timestamp"] = pd.to_datetime(combined["timestamp"], errors="coerce")
    combined["forecast_issue_time"] = pd.to_datetime(
        combined["forecast_issue_time"], errors="coerce"
    )
    combined = combined.dropna(subset=["timestamp", "forecast_issue_time"])
    combined = combined.sort_values(["region", "forecast_issue_time", "timestamp"])
    combined = combined.drop_duplicates(subset=FORECAST_DEDUPE_COLUMNS, keep="last")
    combined = combined[WEATHER_EXPORT_COLUMNS].reset_index(drop=True)
    combined.to_csv(output_path, index=False)

    print(
        f"✅ Appended {len(df_new)} snapshot rows. "
        f"Total rows in {output_path.name}: {len(combined)}"
    )
    return 0


def fetch_weather_forecast_history(
    mode: str = "historical",
    days_to_fetch: int = 730,
    chunk_days: int = 30,
    lead_days: int = 1,
    forecast_hours: int = 24,
    latitude: float | None = None,
    longitude: float | None = None,
    all_vic_regions: bool = False,
    regions: List[str] | None = None,
    fail_on_validation: bool = True,
) -> int:
    settings = load_settings()
    if latitude is not None and longitude is not None:
        locations = [{"name": "site", "latitude": latitude, "longitude": longitude}]
    else:
        locations = resolve_fetch_locations(
            all_vic_regions=all_vic_regions,
            region_names=regions,
            settings=settings,
        )

    if mode == "historical":
        return fetch_historical_forecast_history(
            days_to_fetch=days_to_fetch,
            chunk_days=chunk_days,
            lead_days=lead_days,
            locations=locations,
            fail_on_validation=fail_on_validation,
        )
    if mode == "snapshot":
        return fetch_live_forecast_snapshot(
            locations=locations,
            forecast_hours=forecast_hours,
            fail_on_validation=fail_on_validation,
        )
    raise ValueError("mode must be 'historical' or 'snapshot'.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch weather forecast history (Previous Runs API) or append live forecast snapshots."
        )
    )
    parser.add_argument("--mode", choices=["historical", "snapshot"], default="historical")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--chunk-days", type=int, default=30)
    parser.add_argument("--lead-days", type=int, default=1)
    parser.add_argument("--forecast-hours", type=int, default=24)
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--longitude", type=float, default=None)
    parser.add_argument("--all-vic-regions", action="store_true")
    parser.add_argument("--regions", type=str, default="")
    parser.add_argument("--no-fail-on-validation", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    region_names = [name.strip() for name in args.regions.split(",") if name.strip()] or None
    exit_code = fetch_weather_forecast_history(
        mode=args.mode,
        days_to_fetch=args.days,
        chunk_days=args.chunk_days,
        lead_days=args.lead_days,
        forecast_hours=args.forecast_hours,
        latitude=args.latitude,
        longitude=args.longitude,
        all_vic_regions=args.all_vic_regions,
        regions=region_names,
        fail_on_validation=not args.no_fail_on_validation,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
