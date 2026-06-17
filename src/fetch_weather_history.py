from pathlib import Path
from typing import Dict, List
import argparse
import sys

import pandas as pd
import yaml
from dotenv import load_dotenv

from api_clients.open_meteo import OpenMeteoClient
from config.weather_schema import (
    ACTUAL_DEDUPE_COLUMNS,
    WEATHER_EXPORT_COLUMNS,
    build_date_chunks,
    clip_actual_to_trailing_window,
    finalize_actual_weather_df,
    resolve_fetch_locations,
    validate_actual_weather_df,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
TZ = "Australia/Melbourne"


def load_settings():
    with open(BASE_DIR / "config" / "settings.yaml", "r") as f:
        return yaml.safe_load(f)


def _fetch_actual_for_location(
    *,
    location: Dict,
    days_to_fetch: int,
    chunk_days: int,
    meteo_client: OpenMeteoClient,
    chunks: List[Dict],
) -> pd.DataFrame:
    region = str(location["name"])
    lat = float(location["latitude"])
    lon = float(location["longitude"])
    frames: List[pd.DataFrame] = []

    print(
        f"\n[{region}] Fetching {days_to_fetch} days of actual weather at ({lat}, {lon}) "
        f"in {len(chunks)} chunks ({chunk_days} days each)..."
    )

    for idx, chunk in enumerate(chunks, start=1):
        start_str = chunk["start"].strftime("%Y-%m-%d")
        end_str = chunk["end"].strftime("%Y-%m-%d")
        print(f"  [{idx}/{len(chunks)}] {start_str} -> {end_str}")

        df_chunk = meteo_client.get_historical_weather_df(
            latitude=lat,
            longitude=lon,
            start_date=start_str,
            end_date=end_str,
        )
        if df_chunk is None or df_chunk.empty:
            print("    ⚠️ Chunk returned no data.")
            continue

        frames.append(
            finalize_actual_weather_df(
                df_chunk,
                region=region,
                latitude=lat,
                longitude=lon,
            )
        )
        print(f"    ✅ Rows fetched: {len(df_chunk)}")

    if not frames:
        return pd.DataFrame(columns=WEATHER_EXPORT_COLUMNS)

    df_region = pd.concat(frames, ignore_index=True)
    df_region = df_region.drop_duplicates(subset=ACTUAL_DEDUPE_COLUMNS, keep="last")
    df_region = clip_actual_to_trailing_window(df_region, days_to_fetch=days_to_fetch)
    return df_region.reset_index(drop=True)


def fetch_weather_history(
    days_to_fetch: int = 730,
    chunk_days: int = 30,
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
        df_region = _fetch_actual_for_location(
            location=location,
            days_to_fetch=days_to_fetch,
            chunk_days=chunk_days,
            meteo_client=meteo_client,
            chunks=chunks,
        )
        if df_region.empty:
            print(f"❌ [{location['name']}] No actual weather data fetched.")
            overall_success = False
            continue

        try:
            validate_actual_weather_df(
                df_region,
                region=str(location["name"]),
                expected_start=expected_start,
                expected_end=expected_end,
            )
        except Exception as exc:
            print(f"❌ [{location['name']}] Validation error: {exc}")
            overall_success = False
            if fail_on_validation:
                continue

        region_frames.append(df_region)

    if not region_frames:
        return 1 if fail_on_validation else 0

    df_weather = pd.concat(region_frames, ignore_index=True)
    df_weather = df_weather.drop_duplicates(subset=ACTUAL_DEDUPE_COLUMNS, keep="last")
    df_weather = df_weather.sort_values(["region", "timestamp"]).reset_index(drop=True)

    print(
        f"\nClipped trailing window (Melbourne): "
        f"{window_start.strftime('%Y-%m-%d %H:%M')} -> {now_local.strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"Regions saved: {sorted(df_weather['region'].unique())}")

    if all_vic_regions or (regions and len(regions) > 1):
        output_name = f"weather_actual_vic_{days_to_fetch}d.csv"
    elif len(locations) == 1:
        output_name = f"weather_actual_{locations[0]['name'].lower()}_{days_to_fetch}d.csv"
    else:
        output_name = f"weather_actual_vic_{days_to_fetch}d.csv"

    output_path = raw_dir / output_name
    df_weather.to_csv(output_path, index=False)
    print(f"✅ Saved {len(df_weather)} validated actual weather rows to {output_path.name}")

    if not overall_success and fail_on_validation:
        return 1
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical actual weather from Open-Meteo archive API into CSV."
    )
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--chunk-days", type=int, default=30)
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--longitude", type=float, default=None)
    parser.add_argument(
        "--all-vic-regions",
        action="store_true",
        help="Fetch all five VIC regions from config/locations.py.",
    )
    parser.add_argument(
        "--regions",
        type=str,
        default="",
        help="Comma-separated VIC region names (e.g. Melbourne,Mildura).",
    )
    parser.add_argument("--no-fail-on-validation", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    region_names = [name.strip() for name in args.regions.split(",") if name.strip()] or None
    exit_code = fetch_weather_history(
        days_to_fetch=args.days,
        chunk_days=args.chunk_days,
        latitude=args.latitude,
        longitude=args.longitude,
        all_vic_regions=args.all_vic_regions,
        regions=region_names,
        fail_on_validation=not args.no_fail_on_validation,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
