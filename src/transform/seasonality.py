from __future__ import annotations

import pandas as pd
from statsmodels.tsa.seasonal import STL


def decompose_series(
    frame: pd.DataFrame,
    ticker: str,
    metric: str,
    value_col: str,
    period: int,
    robust: bool = True,
) -> pd.DataFrame:
    data = frame[["date", value_col]].dropna().copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").drop_duplicates("date")
    values = pd.to_numeric(data[value_col], errors="coerce")
    data = data[values.notna()].copy()
    values = values[values.notna()].astype(float)

    if len(data) < period * 2:
        return pd.DataFrame(columns=["ticker", "metric", "date", "value", "trend", "seasonal", "residual"])

    result = STL(values.to_numpy(), period=period, robust=robust).fit()
    return pd.DataFrame({
        "ticker": ticker,
        "metric": metric,
        "date": data["date"].dt.date.to_list(),
        "value": values.to_numpy(),
        "trend": result.trend,
        "seasonal": result.seasonal,
        "residual": result.resid,
    })


def build_seasonality(price: pd.DataFrame, trends: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker, group in price.groupby("ticker"):
        frames.append(decompose_series(group, ticker, "price", "close", period=5))
        frames.append(decompose_series(group, ticker, "volume", "volume", period=5))

    for (ticker, keyword), group in trends.groupby(["ticker", "keyword"]):
        frames.append(decompose_series(group, ticker, f"trends:{keyword}", "interest_score", period=52))

    valid = [frame for frame in frames if not frame.empty]
    return pd.concat(valid, ignore_index=True) if valid else pd.DataFrame(columns=["ticker", "metric", "date", "value", "trend", "seasonal", "residual"])
