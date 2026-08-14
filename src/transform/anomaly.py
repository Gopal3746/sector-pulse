from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_zscore(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    shifted = series.shift(1)
    mean = shifted.rolling(window=window, min_periods=min_periods).mean()
    std = shifted.rolling(window=window, min_periods=min_periods).std(ddof=0).replace(0, np.nan)
    return (series - mean) / std


def detect_anomalies(seasonality: pd.DataFrame, threshold: float = 2.5) -> pd.DataFrame:
    rows = []
    for (ticker, metric), group in seasonality.groupby(["ticker", "metric"], sort=False):
        group = group.sort_values("date").copy()
        is_trends = metric.startswith("trends:")
        window, min_periods = (26, 12) if is_trends else (60, 20)
        group["z_score"] = rolling_zscore(group["residual"].astype(float), window, min_periods)
        group["flagged"] = group["z_score"].abs() > threshold
        direction = np.where(group["z_score"] >= 0, "above", "below")
        group["description"] = [
            f"{ticker} {metric} {abs(z):.1f}σ {d} its trailing residual mean" if pd.notna(z) else "Insufficient trailing history"
            for z, d in zip(group["z_score"], direction)
        ]
        rows.append(group[["ticker", "metric", "date", "value", "z_score", "flagged", "description"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["ticker", "metric", "date", "value", "z_score", "flagged", "description"])
