"""Plotting helpers for forecast evaluation."""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluation.walk_forward import (
    WalkForwardFold,
    WalkForwardResult,
    collect_fold_predictions,
    consolidate_walk_forward_predictions,
)

__all__ = [
    "collect_fold_predictions",
    "consolidate_walk_forward_predictions",
    "plot_actual_vs_predicted_timeseries",
    "plot_actual_vs_predicted_scatter",
    "plot_forecast_window",
    "plot_horizon_mae",
    "plot_result_diagnostics",
]


def plot_actual_vs_predicted_timeseries(
    ts_df: pd.DataFrame,
    *,
    model_name: str,
    title: Optional[str] = None,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Line plot of actual and predicted values over time."""
    ax = ax or plt.gca()
    work = ts_df.sort_values("timestamp")
    ax.plot(work["timestamp"], work["actual"], label="Actual", linewidth=1.2)
    ax.plot(
        work["timestamp"],
        work["predicted"],
        label="Predicted",
        linewidth=1.2,
        linestyle="--",
    )
    ax.set_title(title or f"{model_name}: actual vs predicted over time")
    ax.set_xlabel("Time")
    ax.set_ylabel("$/MWh")
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


def plot_forecast_window(
    fold: WalkForwardFold,
    *,
    model_name: str,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot one 24-hour actual vs predicted window from a walk-forward fold."""
    ax = ax or plt.gca()
    ts = pd.to_datetime(fold.future_timestamps)
    ax.plot(ts, fold.actual, label="Actual", linewidth=2)
    ax.plot(ts, fold.predicted, label="Predicted", linewidth=2, linestyle="--")
    ax.set_title(f"{model_name} @ {fold.origin}")
    ax.set_xlabel("Time")
    ax.set_ylabel("$/MWh")
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


def plot_actual_vs_predicted_scatter(
    pred_df: pd.DataFrame,
    *,
    model_name: str,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Scatter plot of actual vs predicted values."""
    ax = ax or plt.gca()
    subset = pred_df[pred_df["model"] == model_name]
    ax.scatter(subset["actual"], subset["predicted"], alpha=0.15, s=8)
    lo = min(subset["actual"].min(), subset["predicted"].min())
    hi = max(subset["actual"].max(), subset["predicted"].max())
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, label="Perfect forecast")
    ax.set_title(f"{model_name}: actual vs predicted")
    ax.set_xlabel("Actual $/MWh")
    ax.set_ylabel("Predicted $/MWh")
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


def plot_horizon_mae(
    pred_df: pd.DataFrame,
    *,
    model_name: str,
    origin: pd.Timestamp,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """MAE by forecast horizon step for one origin."""
    ax = ax or plt.gca()
    subset = pred_df[
        (pred_df["model"] == model_name) & (pred_df["origin"] == origin)
    ].copy()
    subset = subset.sort_values("timestamp")
    subset["step"] = np.arange(1, len(subset) + 1)
    subset["abs_error"] = (subset["predicted"] - subset["actual"]).abs()
    ax.plot(subset["step"], subset["abs_error"], marker="o", markersize=3)
    ax.set_title(f"{model_name}: |error| by horizon step")
    ax.set_xlabel("Horizon step")
    ax.set_ylabel("Absolute error ($/MWh)")
    ax.grid(alpha=0.3)
    return ax


def plot_result_diagnostics(
    result: WalkForwardResult,
    *,
    sample_origin: Optional[pd.Timestamp] = None,
) -> None:
    """Create a 3-panel diagnostic figure for one walk-forward model."""
    pred_df = collect_fold_predictions(result)
    if pred_df.empty:
        raise ValueError(f"No predictions to plot for {result.model_name}")

    origin = sample_origin or result.folds[len(result.folds) // 2].origin
    fold = next(f for f in result.folds if f.origin == origin)

    fig, axes = plt.subplots(1, 3, figsize=(18, 4))
    plot_forecast_window(fold, model_name=result.model_name, ax=axes[0])
    plot_actual_vs_predicted_scatter(pred_df, model_name=result.model_name, ax=axes[1])
    plot_horizon_mae(pred_df, model_name=result.model_name, origin=origin, ax=axes[2])
    plt.tight_layout()
