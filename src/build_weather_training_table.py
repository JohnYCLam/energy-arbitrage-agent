from pathlib import Path
import argparse
import sys

import pandas as pd

from config.weather_schema import WEATHER_EXPORT_COLUMNS

BASE_DIR = Path(__file__).resolve().parent.parent


def build_weather_training_table(
    *,
    days: int = 730,
    lead_days: int = 1,
    actual_path: Path | None = None,
    forecast_path: Path | None = None,
    output_path: Path | None = None,
) -> int:
    raw_dir = BASE_DIR / "data" / "raw"
    processed_dir = BASE_DIR / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    actual_path = actual_path or raw_dir / f"weather_actual_vic_{days}d.csv"
    forecast_path = forecast_path or raw_dir / f"weather_forecast_history_vic_{days}d_lead{lead_days}d.csv"
    output_path = output_path or processed_dir / "weather_modeling_vic.csv"

    if not actual_path.exists():
        print(f"❌ Missing actual weather file: {actual_path}")
        return 1
    if not forecast_path.exists():
        print(f"❌ Missing forecast history file: {forecast_path}")
        return 1

    actual = pd.read_csv(actual_path)
    forecast = pd.read_csv(forecast_path)

    for df_name, df in [("actual", actual), ("forecast", forecast)]:
        missing = [col for col in WEATHER_EXPORT_COLUMNS if col not in df.columns]
        if missing:
            print(f"❌ {df_name} file missing columns: {missing}")
            return 1

    actual = actual[WEATHER_EXPORT_COLUMNS].copy()
    forecast = forecast[WEATHER_EXPORT_COLUMNS].copy()
    actual["timestamp"] = pd.to_datetime(actual["timestamp"], errors="coerce")
    forecast["timestamp"] = pd.to_datetime(forecast["timestamp"], errors="coerce")
    forecast["forecast_issue_time"] = pd.to_datetime(
        forecast["forecast_issue_time"], errors="coerce"
    )

    combined = pd.concat([actual, forecast], ignore_index=True)
    combined = combined.sort_values(
        ["record_type", "region", "timestamp", "forecast_issue_time"]
    ).reset_index(drop=True)
    combined.to_csv(output_path, index=False)

    actual_min = actual["timestamp"].min()
    actual_max = actual["timestamp"].max()
    forecast_min = forecast["timestamp"].min()
    forecast_max = forecast["timestamp"].max()
    overlap_start = max(actual_min, forecast_min)
    overlap_end = min(actual_max, forecast_max)

    print("Built weather modeling table:")
    print(f"  Actual rows: {len(actual)} | regions: {actual['region'].nunique()}")
    print(f"  Forecast rows: {len(forecast)} | regions: {forecast['region'].nunique()}")
    print(f"  Combined rows: {len(combined)}")
    print(f"  Actual coverage: {actual_min} -> {actual_max}")
    print(f"  Forecast coverage: {forecast_min} -> {forecast_max}")
    print(f"  Modeling overlap window: {overlap_start} -> {overlap_end}")
    print(f"✅ Saved {output_path}")
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine aligned VIC actual + forecast weather CSVs for modeling."
    )
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--lead-days", type=int, default=1)
    parser.add_argument("--actual-path", type=str, default="")
    parser.add_argument("--forecast-path", type=str, default="")
    parser.add_argument("--output-path", type=str, default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    exit_code = build_weather_training_table(
        days=args.days,
        lead_days=args.lead_days,
        actual_path=Path(args.actual_path) if args.actual_path else None,
        forecast_path=Path(args.forecast_path) if args.forecast_path else None,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
