from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.config import configured_pairs, ticker_metadata
from src.transform.anomaly import detect_anomalies
from src.transform.divergence import pair_divergence
from src.transform.seasonality import build_seasonality


def _rng_for(ticker: str) -> np.random.Generator:
    return np.random.default_rng(sum(ord(ch) for ch in ticker) + 2026)


def demo_prices(tickers: list[str], periods: int = 520) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=periods)
    rows = []
    for idx, ticker in enumerate(tickers):
        rng = _rng_for(ticker)
        drift = 0.00025 + idx * 0.000015
        returns = rng.normal(drift, 0.014 + idx * 0.00025, periods)
        # deterministic stress event near the end for anomaly visibility
        if periods > 120:
            returns[-45] += 0.075 if idx % 2 == 0 else -0.065
        close = (70 + idx * 12) * np.exp(np.cumsum(returns))
        open_ = close * (1 + rng.normal(0, 0.003, periods))
        high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.012, periods))
        low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.012, periods))
        volume = rng.integers(2_000_000, 18_000_000, periods)
        for dt, o, h, l, c, v in zip(dates, open_, high, low, close, volume):
            rows.append({"ticker": ticker, "date": dt.date(), "open": o, "high": h, "low": l, "close": c, "volume": int(v)})
    return pd.DataFrame(rows)


def demo_trends(metadata: dict, tickers: list[str], weeks: int = 104) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=weeks, freq="W-SUN")
    rows = []
    for ticker in tickers:
        rng = _rng_for(ticker)
        for keyword_idx, keyword in enumerate(metadata[ticker]["brand_keywords"]):
            t = np.arange(weeks)
            baseline = 45 + 8 * np.sin(2 * np.pi * t / 52 + keyword_idx) + rng.normal(0, 4, weeks)
            baseline[-12] += 28 if keyword_idx == 0 else -18
            values = np.clip(baseline, 0, 100)
            for dt, value in zip(dates, values):
                rows.append({"ticker": ticker, "keyword": keyword, "date": dt.date(), "interest_score": float(value)})
    return pd.DataFrame(rows)


def demo_filings_and_financials(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    filings, financials = [], []
    quarter_ends = pd.to_datetime(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"])
    for idx, ticker in enumerate(tickers):
        rng = _rng_for(ticker)
        base_revenue = (18 + idx * 6) * 1e9
        for q, period_end in enumerate(quarter_ends):
            filing_type = "10-K" if period_end.month == 12 else "10-Q"
            filing_date = period_end + pd.Timedelta(days=35 + (idx % 8))
            accession = f"000{1000000 + idx:07d}-26-{q + 1000:06d}"
            filings.append({"ticker": ticker, "accession_number": accession, "filing_type": filing_type, "filing_date": filing_date.date(), "period_end": period_end.date()})
            revenue = base_revenue * (1 + 0.025 * q) * (1 + rng.normal(0, 0.025))
            for tag, multiplier in [("Revenue", 1.0), ("CostOfGoodsSold", 0.64), ("InventoryNet", 0.18)]:
                financials.append({"ticker": ticker, "tag": tag, "period_end": period_end.date(), "value": float(revenue * multiplier), "filed_date": filing_date.date()})
    return pd.DataFrame(filings), pd.DataFrame(financials)


def build_demo(conn, tickers: list[str] | None = None) -> dict[str, int]:
    from src.db import init_db, load_ticker_dimension, upsert_dataframe

    metadata = ticker_metadata()
    tickers = tickers or list(metadata)
    init_db(conn)
    load_ticker_dimension(conn, {ticker: metadata[ticker] for ticker in tickers})
    prices = demo_prices(tickers)
    trends = demo_trends(metadata, tickers)
    filings, financials = demo_filings_and_financials(tickers)
    seasonality = build_seasonality(prices, trends)
    anomalies = detect_anomalies(seasonality)
    pairs = [p for p in configured_pairs() if p[0] in tickers and p[1] in tickers]
    divergence = pair_divergence(prices, pairs)
    frames = {
        "fact_price": prices,
        "fact_trends": trends,
        "fact_filings": filings,
        "fact_financials": financials,
        "fact_seasonality": seasonality,
        "fact_anomaly": anomalies,
        "fact_pair_divergence": divergence,
    }
    return {table: upsert_dataframe(conn, table, frame) for table, frame in frames.items()}
