"""Walk-forward validation utilities for forecasting models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from config.forecasting import ForecastingConfig, load_forecasting_config

ForecastFn = Callable[[pd.Series, ForecastingConfig], np.ndarray]


@dataclass(frozen=True)
class WalkForwardFold:
    origin: pd.Timestamp
    train_end: pd.Timestamp
    future_timestamps: pd.DatetimeIndex
    actual: np.ndarray
    predicted: np.ndarray


@dataclass(frozen=True)
class WalkForwardResult:
    model_name: str
    folds: List[WalkForwardFold]

    def metrics_frame(self) -> pd.DataFrame:
        rows = []
        for fold in self.folds:
            err = fold.predicted - fold.actual
            rows.append(
                {
                    "origin": fold.origin,
                    "mae": float(np.mean(np.abs(err))),
                    "rmse": float(np.sqrt(np.mean(err**2))),
                }
            )
        return pd.DataFrame(rows)


def _ensure_timestamp_series(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    work = df.copy()
    work[timestamp_col] = pd.to_datetime(work[timestamp_col], errors="coerce")
    work = work.dropna(subset=[timestamp_col]).sort_values(timestamp_col)
    return work


def generate_walk_forward_origins(
    df: pd.DataFrame,
    cfg: ForecastingConfig,
    *,
    timestamp_col: str = "timestamp",
    split: str = "selection",
) -> List[pd.Timestamp]:
    """
    Generate weekly forecast origins for walk-forward validation.

    split:
      - selection: origins in the model-selection window
      - holdout: origins in the final holdout window
    """
    work = _ensure_timestamp_series(df, timestamp_col)
    ts = work[timestamp_col]
    min_ts = ts.min()
    max_ts = ts.max()

    first_origin = min_ts + pd.Timedelta(days=cfg.walk_forward.min_train_days)
    holdout_start = max_ts - pd.Timedelta(days=cfg.walk_forward.holdout_days)
    selection_end = holdout_start - pd.Timedelta(days=cfg.walk_forward.selection_buffer_days)

    if split == "selection":
        start = first_origin
        end = min(selection_end, max_ts - pd.Timedelta(hours=cfg.forecast_horizon_hours))
    elif split == "holdout":
        start = max(first_origin, holdout_start)
        end = max_ts - pd.Timedelta(hours=cfg.forecast_horizon_hours)
    else:
        raise ValueError("split must be 'selection' or 'holdout'")

    if end <= start:
        return []

    origin = start.normalize() + pd.Timedelta(hours=cfg.walk_forward.origin_hour)
    if origin < start:
        origin += pd.Timedelta(days=1)

    origins: List[pd.Timestamp] = []
    while origin <= end:
        origins.append(origin)
        origin += pd.Timedelta(days=cfg.walk_forward.origin_freq_days)
    return origins


def run_walk_forward(
    df: pd.DataFrame,
    *,
    target_col: str,
    forecast_fn: ForecastFn,
    cfg: Optional[ForecastingConfig] = None,
    model_name: str = "model",
    timestamp_col: str = "timestamp",
    min_history_steps: Optional[int] = None,
    split: str = "selection",
) -> WalkForwardResult:
    """Run origin-by-origin walk-forward evaluation for a univariate forecaster."""
    cfg = cfg or load_forecasting_config()
    min_history = min_history_steps or cfg.seasonal_naive_lag
    work = _ensure_timestamp_series(df, timestamp_col)
    work = work.set_index(timestamp_col)
    target = pd.to_numeric(work[target_col], errors="coerce")

    folds: List[WalkForwardFold] = []
    for origin in generate_walk_forward_origins(
        work.reset_index(),
        cfg,
        timestamp_col=timestamp_col,
        split=split,
    ):
        history = target.loc[:origin].dropna()
        future_index = target.loc[origin:].iloc[1 : cfg.forecast_steps + 1]
        if len(history) < min_history or len(future_index) < cfg.forecast_steps:
            continue

        predicted = forecast_fn(history, cfg)
        actual = future_index.iloc[: cfg.forecast_steps].to_numpy(dtype=float)
        predicted = np.asarray(predicted, dtype=float)[: cfg.forecast_steps]

        folds.append(
            WalkForwardFold(
                origin=origin,
                train_end=origin,
                future_timestamps=future_index.index[: cfg.forecast_steps],
                actual=actual,
                predicted=predicted,
            )
        )

    return WalkForwardResult(model_name=model_name, folds=folds)


def collect_fold_predictions(result: WalkForwardResult) -> pd.DataFrame:
    """Flatten walk-forward folds into a long actual-vs-predicted frame."""
    rows = []
    for fold in result.folds:
        for ts, actual, predicted in zip(
            fold.future_timestamps,
            fold.actual,
            fold.predicted,
            strict=True,
        ):
            rows.append(
                {
                    "origin": fold.origin,
                    "timestamp": ts,
                    "actual": actual,
                    "predicted": predicted,
                    "model": result.model_name,
                }
            )
    return pd.DataFrame(rows)


def consolidate_walk_forward_predictions(pred_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse overlapping fold predictions to one row per target timestamp."""
    sorted_df = pred_df.sort_values(["timestamp", "origin"])
    return (
        sorted_df.groupby("timestamp", as_index=False)
        .agg(
            actual=("actual", "first"),
            predicted=("predicted", "last"),
            origin=("origin", "last"),
        )
        .sort_values("timestamp")
    )


def summarize_results(results: Sequence[WalkForwardResult]) -> pd.DataFrame:
    """Aggregate MAE/RMSE across models."""
    rows = []
    for result in results:
        metrics = result.metrics_frame()
        if metrics.empty:
            continue
        rows.append(
            {
                "model": result.model_name,
                "folds": len(metrics),
                "mae_mean": metrics["mae"].mean(),
                "rmse_mean": metrics["rmse"].mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("mae_mean")
