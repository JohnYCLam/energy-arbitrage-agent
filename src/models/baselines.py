"""Baseline forecasters for price prediction."""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from config.forecasting import ForecastingConfig


def persistence_forecast(last_price: float, cfg: ForecastingConfig) -> np.ndarray:
    """Repeat the last observed price for the full horizon."""
    return np.full(cfg.forecast_steps, last_price, dtype=float)


def seasonal_naive_forecast(history: pd.Series, cfg: ForecastingConfig) -> np.ndarray:
    """Use prices from the same time slots one day earlier."""
    lag = cfg.seasonal_naive_lag
    if len(history) < lag:
        last = float(history.iloc[-1])
        return persistence_forecast(last, cfg)

    values = history.iloc[-lag:].to_numpy(dtype=float)
    if len(values) < cfg.forecast_steps:
        last = float(history.iloc[-1])
        padded = np.full(cfg.forecast_steps, last, dtype=float)
        padded[: len(values)] = values
        return padded
    return values[: cfg.forecast_steps]


ForecastFn = Callable[[pd.Series, ForecastingConfig], np.ndarray]


def get_baseline_forecast_fn(name: str) -> ForecastFn:
    """Return a baseline forecasting function by name."""
    baselines: dict[str, ForecastFn] = {
        "persistence": lambda history, cfg: persistence_forecast(float(history.iloc[-1]), cfg),
        "seasonal_naive": seasonal_naive_forecast,
    }
    key = name.lower()
    if key not in baselines:
        raise ValueError(f"Unknown baseline: {name}")
    return baselines[key]
