"""Tests for forecasting configuration and walk-forward utilities."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from config.forecasting import load_forecasting_config
from evaluation.walk_forward import generate_walk_forward_origins, run_walk_forward
from models.baselines import get_baseline_forecast_fn

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"


def test_forecasting_config_derived_values():
    cfg = load_forecasting_config()
    assert cfg.forecast_steps == cfg.forecast_horizon_hours * 60 // cfg.interval_minutes
    assert cfg.input_chunk_length == cfg.input_chunk_days * 24 * 60 // cfg.interval_minutes
    assert cfg.pandas_freq == f"{cfg.interval_minutes}min"
    assert cfg.seasonal_naive_lag == cfg.steps_per_day


def test_baseline_forecast_shapes():
    cfg = load_forecasting_config()
    history = pd.Series(range(cfg.input_chunk_length))
    persistence = get_baseline_forecast_fn("persistence")(history, cfg)
    seasonal = get_baseline_forecast_fn("seasonal_naive")(history, cfg)
    assert len(persistence) == cfg.forecast_steps
    assert len(seasonal) == cfg.forecast_steps


def test_walk_forward_generates_origins():
    cfg = load_forecasting_config()
    days = cfg.walk_forward.min_train_days + cfg.walk_forward.holdout_days + 30
    freq = cfg.pandas_freq
    index = pd.date_range("2023-01-01", periods=days * cfg.steps_per_day, freq=freq, tz=cfg.timezone)
    df = pd.DataFrame({"timestamp": index, "vic1_price": range(len(index))})
    origins = generate_walk_forward_origins(df, cfg, split="selection")
    assert len(origins) > 0


def test_walk_forward_runs_persistence():
    cfg = load_forecasting_config()
    periods = (cfg.walk_forward.min_train_days + cfg.walk_forward.holdout_days + 30) * cfg.steps_per_day
    index = pd.date_range("2023-01-01", periods=periods, freq=cfg.pandas_freq, tz=cfg.timezone)
    df = pd.DataFrame({"timestamp": index, "vic1_price": 50.0})
    result = run_walk_forward(
        df,
        target_col="vic1_price",
        forecast_fn=get_baseline_forecast_fn("persistence"),
        cfg=cfg,
        model_name="persistence",
        split="selection",
    )
    assert len(result.folds) > 0
    assert result.metrics_frame()["mae"].mean() == pytest.approx(0.0)


@pytest.mark.parametrize(
    "pattern",
    [
        r"output_chunk_length\s*=\s*96",
        r"input_chunk_length\s*=\s*672",
        r"resample\(['\"]30min['\"]\)",
    ],
)
def test_no_hardcoded_horizons_in_models_or_eval(pattern: str):
    targets = [
        SRC_DIR / "models" / "baselines.py",
        SRC_DIR / "models" / "align_timeseries.py",
        SRC_DIR / "evaluation" / "walk_forward.py",
        SRC_DIR / "build_price_training_table.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in targets if path.exists())
    assert re.search(pattern, combined) is None
