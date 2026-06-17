from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import argparse
import sys

import pandas as pd
import yaml
from dotenv import load_dotenv

# Load API Clients
from api_clients.pricing_api import OpenNEMClient

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def load_settings():
    with open(BASE_DIR / "config" / "settings.yaml", "r") as f:
        return yaml.safe_load(f)

def _floor_utc_to_interval(ts: datetime, interval_minutes: int) -> datetime:
    """Floors a UTC timestamp down to the previous interval boundary."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    floored_minute = (ts.minute // interval_minutes) * interval_minutes
    return ts.replace(minute=floored_minute, second=0, microsecond=0)


def _build_date_chunks(days_to_fetch: int, chunk_days: int) -> List[Dict[str, datetime]]:
    end_date = _floor_utc_to_interval(datetime.now(timezone.utc), interval_minutes=5)
    start_date = end_date - timedelta(days=days_to_fetch)
    chunks: List[Dict[str, datetime]] = []

    cursor = start_date
    while cursor < end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days), end_date)
        chunks.append({"start": cursor, "end": chunk_end})
        cursor = chunk_end

    return chunks


def _validate_energy_df(
    df: pd.DataFrame,
    *,
    region: str,
    expected_start: datetime,
    expected_end: datetime,
    interval_minutes: int = 5,
) -> None:
    if df.empty:
        raise ValueError(f"[{region}] Validation failed: dataframe is empty.")

    df = df.copy()
    df["interval"] = pd.to_datetime(df["interval"], utc=True, errors="coerce")
    if df["interval"].isna().all():
        raise ValueError(f"[{region}] Validation failed: all interval timestamps are invalid.")

    df = df.dropna(subset=["interval"]).sort_values("interval")
    min_ts = df["interval"].min()
    max_ts = df["interval"].max()
    expected_start_utc = pd.Timestamp(expected_start)
    expected_end_utc = pd.Timestamp(expected_end)
    if expected_start_utc.tzinfo is None:
        expected_start_utc = expected_start_utc.tz_localize("UTC")
    else:
        expected_start_utc = expected_start_utc.tz_convert("UTC")
    if expected_end_utc.tzinfo is None:
        expected_end_utc = expected_end_utc.tz_localize("UTC")
    else:
        expected_end_utc = expected_end_utc.tz_convert("UTC")

    expected_intervals = int((expected_end - expected_start).total_seconds() // (interval_minutes * 60))
    unique_intervals = df["interval"].nunique()
    missing_intervals = max(expected_intervals - unique_intervals, 0)
    duplicate_rows = int(df.duplicated(subset=["interval"]).sum())
    null_ratio = df.isna().mean().sort_values(ascending=False).head(5)

    print(f"[{region}] Validation summary:")
    print(f"  Coverage: {min_ts} -> {max_ts}")
    print(
        f"  Expected ~{expected_intervals} intervals @ {interval_minutes}m, "
        f"got {unique_intervals} unique (missing ~{missing_intervals})"
    )
    print(f"  Duplicate interval rows: {duplicate_rows}")
    print("  Top null ratios:")
    for column, ratio in null_ratio.items():
        print(f"    - {column}: {ratio:.2%}")

    if min_ts > expected_start_utc + pd.Timedelta(hours=6):
        raise ValueError(
            f"[{region}] Validation failed: data starts too late ({min_ts}) for requested window."
        )
    if max_ts < expected_end_utc - pd.Timedelta(hours=6):
        raise ValueError(
            f"[{region}] Validation failed: data ends too early ({max_ts}) for requested window."
        )


def fetch_energy_history(
    days_to_fetch: int = 730,
    chunk_days: int = 7,
    regions: List[str] | None = None,
    fail_on_validation: bool = True,
) -> int:
    if chunk_days <= 0:
        raise ValueError("chunk_days must be greater than 0.")

    settings = load_settings()
    primary_region = settings["market"]["nem_region"]
    adjacent_regions = settings["market"].get("adjacent_regions", [])

    if regions is not None and len(regions) > 0:
        # Explicit override from CLI
        all_regions = regions
    else:
        all_regions = [primary_region] + adjacent_regions

    # Ensure output directory exists
    raw_dir = BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    pricing_client = OpenNEMClient()
    chunks = _build_date_chunks(days_to_fetch=days_to_fetch, chunk_days=chunk_days)
    if not chunks:
        raise ValueError("No chunks were generated; check days_to_fetch and chunk_days.")

    overall_start = chunks[0]["start"]
    overall_end = chunks[-1]["end"]

    overall_success = True

    for region in all_regions:
        print(
            f"\nFetching {days_to_fetch} days of historical market data for {region} "
            f"in {len(chunks)} chunks ({chunk_days} days each)..."
        )
        region_frames: List[pd.DataFrame] = []

        for idx, chunk in enumerate(chunks, start=1):
            chunk_start = chunk["start"]
            chunk_end = chunk["end"]
            print(
                f"  [{idx}/{len(chunks)}] {chunk_start.strftime('%Y-%m-%d %H:%M')} "
                f"-> {chunk_end.strftime('%Y-%m-%d %H:%M')}"
            )

            df_chunk = pricing_client.get_regional_energy_data_range(
                nem_region=region,
                start_date=chunk_start,
                end_date=chunk_end,
            )
            if df_chunk is None or df_chunk.empty:
                print("    ⚠️ Chunk returned no data.")
                continue

            region_frames.append(df_chunk)
            print(f"    ✅ Rows fetched: {len(df_chunk)}")

        if not region_frames:
            msg = f"[{region}] No data fetched across any chunk."
            print(f"❌ {msg}")
            overall_success = False
            if fail_on_validation:
                continue
            else:
                continue

        df_merged = pd.concat(region_frames, ignore_index=True)
        df_merged["interval"] = pd.to_datetime(df_merged["interval"], utc=True, errors="coerce")
        df_merged = df_merged.dropna(subset=["interval"]).sort_values("interval")
        df_merged = df_merged.drop_duplicates(subset=["interval"], keep="last").reset_index(drop=True)

        try:
            _validate_energy_df(
                df_merged,
                region=region,
                expected_start=overall_start,
                expected_end=overall_end,
                interval_minutes=5,
            )
        except Exception as exc:
            print(f"❌ [{region}] Validation error: {exc}")
            overall_success = False
            if fail_on_validation:
                continue

        market_path = raw_dir / f"market_{region}_{days_to_fetch}d.csv"
        df_merged.to_csv(market_path, index=False)
        print(f"✅ Saved {len(df_merged)} validated market records to {market_path.name}")

    if not overall_success and fail_on_validation:
        return 1
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical NEM market + network data into CSV files."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Total number of days of history to fetch (default: 730).",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=7,
        help="Number of days per API chunk (default: 7).",
    )
    parser.add_argument(
        "--regions",
        type=str,
        default="",
        help=(
            "Comma-separated list of NEM regions to fetch. "
            "If omitted, uses settings.yaml nem_region + adjacent_regions."
        ),
    )
    parser.add_argument(
        "--no-fail-on-validation",
        action="store_true",
        help=(
            "Do not exit with non-zero status on validation errors. "
            "Useful for exploratory runs."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    regions: List[str] | None = None
    if args.regions:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]

    exit_code = fetch_energy_history(
        days_to_fetch=args.days,
        chunk_days=args.chunk_days,
        regions=regions,
        fail_on_validation=not args.no_fail_on_validation,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()