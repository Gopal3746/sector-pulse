from __future__ import annotations

import numpy as np
import pandas as pd

from src.transform.anomaly import rolling_zscore


def pair_divergence(price: pd.DataFrame, pairs: list[tuple[str, str]], threshold: float = 2.5) -> pd.DataFrame:
    close = price.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
    returns = close.pct_change(fill_method=None)
    rows = []
    for ticker_a, ticker_b in pairs:
        if ticker_a not in returns or ticker_b not in returns:
            continue
        frame = pd.DataFrame({"return_a": returns[ticker_a], "return_b": returns[ticker_b]}).dropna()
        frame["divergence"] = frame["return_a"] - frame["return_b"]
        frame["z_score"] = rolling_zscore(frame["divergence"], window=60, min_periods=20)
        frame["flagged"] = frame["z_score"].abs() > threshold
        frame = frame.reset_index().rename(columns={frame.index.name or "index": "date"})
        frame["pair"] = f"{ticker_a}/{ticker_b}"
        frame["ticker_a"] = ticker_a
        frame["ticker_b"] = ticker_b
        rows.append(frame[["pair", "ticker_a", "ticker_b", "date", "return_a", "return_b", "divergence", "z_score", "flagged"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["pair", "ticker_a", "ticker_b", "date", "return_a", "return_b", "divergence", "z_score", "flagged"])
