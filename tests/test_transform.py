import numpy as np
import pandas as pd

from src.transform.anomaly import detect_anomalies
from src.transform.divergence import pair_divergence
from src.transform.seasonality import decompose_series


def test_seasonality_decomposition_returns_components():
    n = 120
    frame = pd.DataFrame({"date": pd.bdate_range("2025-01-01", periods=n), "close": 100 + np.sin(np.arange(n) * 2 * np.pi / 5) + np.arange(n) * 0.02})
    result = decompose_series(frame, "TST", "price", "close", period=5)
    assert len(result) == n
    assert {"trend", "seasonal", "residual"}.issubset(result.columns)


def test_anomaly_detector_flags_large_residual_spike():
    n = 100
    residual = np.zeros(n)
    residual[:80] = np.linspace(-1, 1, 80)
    residual[-1] = 20
    seasonality = pd.DataFrame({
        "ticker": ["TST"] * n, "metric": ["price"] * n,
        "date": pd.bdate_range("2025-01-01", periods=n).date,
        "value": np.arange(n, dtype=float), "trend": np.arange(n), "seasonal": 0.0, "residual": residual,
    })
    result = detect_anomalies(seasonality)
    assert bool(result.iloc[-1]["flagged"])
    assert result.iloc[-1]["z_score"] > 2.5


def test_pair_divergence_outputs_pair():
    dates = pd.bdate_range("2025-01-01", periods=100)
    a = 100 * np.cumprod(np.repeat(1.001, 100))
    b = 100 * np.cumprod(np.repeat(1.0005, 100))
    price = pd.concat([
        pd.DataFrame({"ticker": "AAA", "date": dates.date, "close": a}),
        pd.DataFrame({"ticker": "BBB", "date": dates.date, "close": b}),
    ], ignore_index=True)
    result = pair_divergence(price, [("AAA", "BBB")])
    assert not result.empty
    assert result.iloc[0]["pair"] == "AAA/BBB"
