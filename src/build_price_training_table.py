"""Build the joint energy + weather price modeling table."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

import pandas as pd

from config.forecasting import ForecastingConfig, load_forecasting_config
from config.weather_schema import WEATHER_EXPORT_COLUMNS
from models.align_timeseries import (
    add_calendar_features,
    align_weather_df,
    load_and_align_energy_csv,
    merge_energy_weather,
    merge_regional_energy,
    region_slug,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_weather_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [col for col in WEATHER_EXPORT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Weather file {path} missing columns: {missing}")
    return df[WEATHER_EXPORT_COLUMNS].copy()


def _prepare_forecast_weather(df: pd.DataFrame) -> pd.DataFrame:
    work = df[df["record_type"] == "forecast"].copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work["forecast_issue_time"] = pd.to_datetime(work["forecast_issue_time"], errors="coerce")
    work = work.dropna(subset=["timestamp", "forecast_issue_time"])
    work = work.sort_values(["region", "timestamp", "forecast_issue_time"])
    work = work.drop_duplicates(subset=["region", "timestamp"], keep="last")
    return work


def _prepare_actual_weather(df: pd.DataFrame) -> pd.DataFrame:
    work = df[df["record_type"] == "actual"].copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp"])
    work = work.sort_values(["region", "timestamp"])
    work = work.drop_duplicates(subset=["region", "timestamp"], keep="last")
    return work


def validate_no_obvious_leakage(df: pd.DataFrame, *, target_col: str, cfg: ForecastingConfig) -> None:
    """Fail fast if a feature column equals a future-shifted target."""
    if target_col not in df.columns:
        raise ValueError(f"Missing target column: {target_col}")

    target = pd.to_numeric(df[target_col], errors="coerce")
    for col in df.columns:
        if col == target_col or col == "timestamp":
            continue
        if not col.endswith("_forecast") and col not in {"hour", "day_of_week", "is_weekend", "month"}:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.isna().all():
            continue
        future_target = target.shift(-1)
        overlap = series.notna() & future_target.notna()
        if not overlap.any():
            continue
        corr = series[overlap].corr(future_target[overlap])
        if corr is not None and corr > 0.9999:
            raise ValueError(
                f"Possible leakage: {col} is almost perfectly correlated with next-step {target_col}."
            )

    lag = cfg.seasonal_naive_lag
    if len(df) > lag:
        shifted = target.shift(-lag)
        overlap = target.notna() & shifted.notna()
        if overlap.any() and target[overlap].corr(shifted[overlap]) > 0.9999:
            raise ValueError("Target series failed basic lag sanity check.")


def build_price_training_table(
    *,
    days: int = 730,
    lead_days: int = 1,
    cfg: ForecastingConfig | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Merge aligned energy, weather, and calendar features for modeling."""
    cfg = cfg or load_forecasting_config()
    raw_dir = BASE_DIR / "data" / "raw"
    processed_dir = BASE_DIR / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_path or processed_dir / f"price_modeling_vic_{days}d.csv"

    energy_frames = []
    for region in cfg.all_regions:
        path = raw_dir / f"market_{region}_{days}d.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing energy file: {path}")
        energy_frames.append(load_and_align_energy_csv(path, region, cfg))

    energy = merge_regional_energy(energy_frames)

    actual_path = raw_dir / f"weather_actual_vic_{days}d.csv"
    forecast_path = raw_dir / f"weather_forecast_history_vic_{days}d_lead{lead_days}d.csv"
    if not actual_path.exists():
        raise FileNotFoundError(f"Missing actual weather file: {actual_path}")
    if not forecast_path.exists():
        raise FileNotFoundError(f"Missing forecast weather file: {forecast_path}")

    actual_weather = _prepare_actual_weather(_load_weather_csv(actual_path))
    forecast_weather = _prepare_forecast_weather(_load_weather_csv(forecast_path))

    weather_actual = align_weather_df(actual_weather, cfg, column_suffix="actual")
    weather_forecast = align_weather_df(forecast_weather, cfg, column_suffix="forecast")

    merged = merge_energy_weather(energy, weather_actual, cfg)
    merged = merged.join(weather_forecast, how="inner")
    merged = add_calendar_features(merged, cfg)

    target_col = f"{region_slug(cfg.target_region)}_price"
    merged = merged.dropna(subset=[target_col])
    merged = merged.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in merged.columns:
        merged = merged.rename(columns={merged.columns[0]: "timestamp"})

    validate_no_obvious_leakage(merged, target_col=target_col, cfg=cfg)

    # Naive local timestamps serialize cleanly for notebook CSV loads.
    merged["timestamp"] = (
        pd.to_datetime(merged["timestamp"], utc=True)
        .dt.tz_convert(cfg.timezone)
        .dt.tz_localize(None)
    )
    merged.to_csv(output_path, index=False)

    print("Built price modeling table:")
    print(f"  Grid: {cfg.pandas_freq} ({cfg.interval_minutes}-minute)")
    print(f"  Rows: {len(merged)}")
    print(f"  Columns: {len(merged.columns)}")
    print(f"  Target: {target_col}")
    print(f"  Coverage: {merged['timestamp'].min()} -> {merged['timestamp'].max()}")
    print(f"Saved {output_path}")
    return merged


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build aligned VIC price modeling table from energy + weather CSVs."
    )
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--lead-days", type=int, default=1)
    parser.add_argument("--output-path", type=str, default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        build_price_training_table(
            days=args.days,
            lead_days=args.lead_days,
            output_path=Path(args.output_path) if args.output_path else None,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
