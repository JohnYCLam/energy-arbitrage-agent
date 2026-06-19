"""Align energy and weather time series to the configured forecasting grid."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import pandas as pd

from config.forecasting import ForecastingConfig
from config.weather_schema import WEATHER_FEATURE_COLUMNS

ENERGY_VALUE_COLUMNS = (
    "price",
    "demand",
    "renewable_generation",
    "interconnector_flow_mw",
)


def region_slug(region: str) -> str:
    """Convert NEM region code to a lowercase column prefix."""
    return region.lower().replace(" ", "_")


def weather_region_slug(name: str) -> str:
    """Convert a weather location name to a lowercase column prefix."""
    return name.lower().replace(" ", "_")


def normalize_energy_timestamps(
    df: pd.DataFrame,
    *,
    cfg: ForecastingConfig,
    timestamp_col: str = "interval",
) -> pd.DataFrame:
    """Parse energy interval timestamps and convert to the config timezone."""
    work = df.copy()
    if timestamp_col not in work.columns:
        raise ValueError(f"Energy dataframe missing timestamp column: {timestamp_col}")

    work["timestamp"] = pd.to_datetime(work[timestamp_col], utc=True, errors="coerce")
    work = work.dropna(subset=["timestamp"])
    work["timestamp"] = work["timestamp"].dt.tz_convert(cfg.timezone)
    return work.drop(columns=[timestamp_col])


def normalize_live_energy_df(df_price: pd.DataFrame, *, cfg: ForecastingConfig) -> pd.DataFrame:
    """Normalize live OpenElectricity energy rows (interval/price/demand columns)."""
    col_map = {
        col: "timestamp"
        for col in df_price.columns
        if "interval" in str(col).lower() or "time" in str(col).lower()
    }
    col_map.update(
        {
            col: "spot_price"
            for col in df_price.columns
            if "value" in str(col).lower() or "price" in str(col).lower()
        }
    )
    col_map.update(
        {col: "demand" for col in df_price.columns if "demand" in str(col).lower()}
    )

    normalized = df_price.rename(columns=col_map).copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True, errors="coerce")
    normalized = normalized.dropna(subset=["timestamp"])
    normalized["timestamp"] = normalized["timestamp"].dt.tz_convert(cfg.timezone)
    return normalized


def _energy_numeric_columns(df: pd.DataFrame) -> list[str]:
    cols = [
        c
        for c in df.columns
        if c in ENERGY_VALUE_COLUMNS or c in {"spot_price"} or str(c).startswith("gen_")
    ]
    return cols


def align_energy_df(
    df: pd.DataFrame,
    cfg: ForecastingConfig,
    *,
    region_prefix: Optional[str] = None,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Resample energy data to cfg.pandas_freq.

    When interval_minutes equals energy_native_minutes, only deduplicates.
    """
    if timestamp_col not in df.columns:
        raise ValueError(f"Energy dataframe missing {timestamp_col}")

    work = df.copy()
    work[timestamp_col] = pd.to_datetime(work[timestamp_col], errors="coerce")
    if work[timestamp_col].dt.tz is None:
        work[timestamp_col] = work[timestamp_col].dt.tz_localize(
            cfg.timezone,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
    work = work.dropna(subset=[timestamp_col]).sort_values(timestamp_col)
    work = work.drop_duplicates(subset=[timestamp_col], keep="last")
    work = work.set_index(timestamp_col)

    numeric_cols = _energy_numeric_columns(work)
    if not numeric_cols:
        raise ValueError("No numeric energy columns found to align.")

    work[numeric_cols] = work[numeric_cols].apply(pd.to_numeric, errors="coerce")

    if (
        cfg.interval_minutes == cfg.energy_native_minutes
        or cfg.energy_resample == "none"
    ):
        aligned = work[numeric_cols]
    else:
        if cfg.energy_resample != "mean":
            raise ValueError(f"Unsupported energy_resample: {cfg.energy_resample}")
        aligned = work[numeric_cols].resample(cfg.pandas_freq).mean()

    aligned = aligned.dropna(how="all")
    if region_prefix:
        aligned = aligned.rename(
            columns={col: f"{region_prefix}_{col}" for col in aligned.columns}
        )
    return aligned


def localize_weather_timestamps(df: pd.DataFrame, cfg: ForecastingConfig) -> pd.DataFrame:
    """Localize naive weather timestamps to the config timezone."""
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp"])
    if work["timestamp"].dt.tz is None:
        work["timestamp"] = work["timestamp"].dt.tz_localize(
            cfg.timezone,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
    else:
        work["timestamp"] = work["timestamp"].dt.tz_convert(cfg.timezone)
    return work


def pivot_weather_wide(
    df: pd.DataFrame,
    *,
    column_suffix: str = "",
    feature_columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Pivot long weather rows (region × timestamp) to wide feature columns."""
    features = list(feature_columns or WEATHER_FEATURE_COLUMNS)
    work = df.copy()
    if "region" not in work.columns:
        # Single-location observations (live API) — keep unprefixed names.
        indexed = work.set_index("timestamp")
        return indexed[features]

    work["region_slug"] = work["region"].map(weather_region_slug)
    frames = []
    for region_name, group in work.groupby("region_slug"):
        wide = group.set_index("timestamp")[features].copy()
        suffix = f"_{column_suffix}" if column_suffix else ""
        wide = wide.rename(columns={col: f"{region_name}_{col}{suffix}" for col in features})
        frames.append(wide)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, axis=1).sort_index()


def _upsample_weather(wide: pd.DataFrame, cfg: ForecastingConfig) -> pd.DataFrame:
    if cfg.weather_upsample == "interpolate":
        upsampled = wide.resample(cfg.pandas_freq).interpolate(method="time")
    elif cfg.weather_upsample == "ffill":
        upsampled = wide.resample(cfg.pandas_freq).ffill()
    else:
        raise ValueError(f"Unsupported weather_upsample: {cfg.weather_upsample}")

    if cfg.weather_solar_clip_zero:
        for col in upsampled.columns:
            if "solar_irradiance" in col:
                upsampled[col] = upsampled[col].clip(lower=0)
    return upsampled


def align_weather_df(df: pd.DataFrame, cfg: ForecastingConfig, *, column_suffix: str = "") -> pd.DataFrame:
    """Localize, pivot (if needed), and upsample weather to cfg.pandas_freq."""
    work = localize_weather_timestamps(df, cfg)
    wide = pivot_weather_wide(work, column_suffix=column_suffix)
    if wide.empty:
        return wide
    return _upsample_weather(wide, cfg)


def merge_energy_weather(
    energy: pd.DataFrame,
    weather: pd.DataFrame,
    cfg: ForecastingConfig,
) -> pd.DataFrame:
    """Inner-join aligned energy and weather frames on the datetime index."""
    merged = pd.merge(
        energy,
        weather,
        left_index=True,
        right_index=True,
        how="inner",
    )
    return merged.sort_index()


def add_calendar_features(df: pd.DataFrame, cfg: ForecastingConfig) -> pd.DataFrame:
    """Add calendar features derived from the datetime index."""
    work = df.copy()
    index = work.index
    if index.tz is None:
        index = index.tz_localize(cfg.timezone, ambiguous="NaT", nonexistent="shift_forward")
    local = index.tz_convert(cfg.timezone)

    work["hour"] = local.hour
    work["day_of_week"] = local.dayofweek
    work["is_weekend"] = (local.dayofweek >= 5).astype(int)
    work["month"] = local.month
    return work


def load_and_align_energy_csv(
    path,
    region: str,
    cfg: ForecastingConfig,
) -> pd.DataFrame:
    """Load a market CSV and return an aligned, prefixed energy frame."""
    raw = pd.read_csv(path)
    normalized = normalize_energy_timestamps(raw, cfg=cfg, timestamp_col="interval")
    if "price" in normalized.columns:
        pass
    elif "spot_price" in normalized.columns:
        normalized = normalized.rename(columns={"spot_price": "price"})
    return align_energy_df(
        normalized,
        cfg,
        region_prefix=region_slug(region),
        timestamp_col="timestamp",
    )


def merge_regional_energy(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Outer-merge multiple regional energy frames on timestamp index."""
    merged: Optional[pd.DataFrame] = None
    for frame in frames:
        merged = frame if merged is None else merged.join(frame, how="outer")
    if merged is None:
        return pd.DataFrame()
    return merged.sort_index()
