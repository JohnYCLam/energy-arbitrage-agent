"""Load forecasting grid settings and derive horizon / chunk lengths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "forecasting.yaml"


@dataclass(frozen=True)
class WalkForwardSettings:
    origin_freq_days: int
    origin_hour: int
    min_train_days: int
    holdout_days: int
    selection_buffer_days: int


@dataclass(frozen=True)
class ArbitrageSettings:
    peak_trough_slots_per_day: int


@dataclass(frozen=True)
class ForecastingConfig:
    timezone: str
    interval_minutes: int
    forecast_horizon_hours: int
    input_chunk_days: int
    energy_native_minutes: int
    weather_native_minutes: int
    energy_resample: str
    weather_upsample: str
    weather_solar_clip_zero: bool
    walk_forward: WalkForwardSettings
    arbitrage: ArbitrageSettings
    target_region: str
    adjacent_regions: List[str]
    model: Dict[str, Any]

    @property
    def forecast_steps(self) -> int:
        return self.forecast_horizon_hours * 60 // self.interval_minutes

    @property
    def input_chunk_length(self) -> int:
        return self.input_chunk_days * 24 * 60 // self.interval_minutes

    @property
    def pandas_freq(self) -> str:
        return f"{self.interval_minutes}min"

    @property
    def seasonal_naive_lag(self) -> int:
        return 24 * 60 // self.interval_minutes

    @property
    def steps_per_day(self) -> int:
        return 24 * 60 // self.interval_minutes

    @property
    def all_regions(self) -> List[str]:
        return [self.target_region, *self.adjacent_regions]

    def validate(self) -> None:
        if self.interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive.")
        if 24 * 60 % self.interval_minutes != 0:
            raise ValueError("interval_minutes must divide evenly into 24 hours.")
        if self.forecast_horizon_hours * 60 % self.interval_minutes != 0:
            raise ValueError("forecast horizon must resolve to whole steps.")
        if self.weather_upsample not in {"interpolate", "ffill"}:
            raise ValueError("weather_upsample must be 'interpolate' or 'ffill'.")
        if self.energy_resample not in {"mean", "none"}:
            raise ValueError("energy_resample must be 'mean' or 'none'.")


def _parse_walk_forward(raw: Dict[str, Any]) -> WalkForwardSettings:
    return WalkForwardSettings(
        origin_freq_days=int(raw["origin_freq_days"]),
        origin_hour=int(raw["origin_hour"]),
        min_train_days=int(raw["min_train_days"]),
        holdout_days=int(raw["holdout_days"]),
        selection_buffer_days=int(raw.get("selection_buffer_days", 0)),
    )


def _parse_arbitrage(raw: Dict[str, Any]) -> ArbitrageSettings:
    return ArbitrageSettings(
        peak_trough_slots_per_day=int(raw["peak_trough_slots_per_day"]),
    )


def load_forecasting_config(
    path: Optional[Path] = None,
) -> ForecastingConfig:
    """Load forecasting.yaml and return a validated config object."""
    config_path = path or DEFAULT_CONFIG_PATH
    with open(config_path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    regions = raw.get("regions", {})
    cfg = ForecastingConfig(
        timezone=str(raw.get("timezone", "Australia/Melbourne")),
        interval_minutes=int(raw["interval_minutes"]),
        forecast_horizon_hours=int(raw["forecast_horizon_hours"]),
        input_chunk_days=int(raw["input_chunk_days"]),
        energy_native_minutes=int(raw.get("energy_native_minutes", 5)),
        weather_native_minutes=int(raw.get("weather_native_minutes", 60)),
        energy_resample=str(raw.get("energy_resample", "mean")),
        weather_upsample=str(raw.get("weather_upsample", "interpolate")),
        weather_solar_clip_zero=bool(raw.get("weather_solar_clip_zero", True)),
        walk_forward=_parse_walk_forward(raw["walk_forward"]),
        arbitrage=_parse_arbitrage(raw["arbitrage"]),
        target_region=str(regions.get("target", "VIC1")),
        adjacent_regions=list(regions.get("adjacent", ["NSW1", "SA1"])),
        model=dict(raw.get("model", {})),
    )
    cfg.validate()
    return cfg
