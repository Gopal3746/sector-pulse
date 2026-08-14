from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import Iterable

import pandas as pd


def _cache_path(cache_dir: Path, ticker: str, keywords: list[str], timeframe: str, geo: str) -> Path:
    digest = hashlib.sha1(json.dumps([ticker, keywords, timeframe, geo]).encode()).hexdigest()[:12]
    return cache_dir / f"{ticker}_{digest}.csv"


def _normalize(ticker: str, keywords: list[str], raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["ticker", "keyword", "date", "interest_score"])
    frame = raw.drop(columns=["isPartial"], errors="ignore").reset_index()
    date_col = "date" if "date" in frame.columns else frame.columns[0]
    melted = frame.melt(id_vars=[date_col], value_vars=[k for k in keywords if k in frame.columns], var_name="keyword", value_name="interest_score")
    melted = melted.rename(columns={date_col: "date"})
    melted["date"] = pd.to_datetime(melted["date"]).dt.date
    melted.insert(0, "ticker", ticker.upper())
    melted["interest_score"] = pd.to_numeric(melted["interest_score"], errors="coerce")
    return melted.dropna(subset=["interest_score"])[["ticker", "keyword", "date", "interest_score"]]


def fetch_ticker_trends(
    ticker: str,
    keywords: Iterable[str],
    timeframe: str = "today 2-y",
    geo: str = "US",
    cache_dir: str | Path = "data/raw/trends",
    retries: int = 4,
    base_delay: float = 5.0,
    force: bool = False,
) -> pd.DataFrame:
    keywords = list(keywords)[:5]
    if not keywords:
        return pd.DataFrame(columns=["ticker", "keyword", "date", "interest_score"])

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(cache_dir, ticker, keywords, timeframe, geo)
    if cached.exists() and not force:
        frame = pd.read_csv(cached, parse_dates=["date"])
        frame["date"] = frame["date"].dt.date
        return frame

    try:
        from pytrends.request import TrendReq
    except ImportError as exc:
        raise RuntimeError("pytrends is required for live Trends ingestion. Install requirements.txt.") from exc

    error: Exception | None = None
    for attempt in range(retries):
        try:
            client = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
            client.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo, gprop="")
            frame = _normalize(ticker, keywords, client.interest_over_time())
            frame.to_csv(cached, index=False)
            return frame
        except Exception as exc:  # pytrends wraps multiple HTTP exception types
            error = exc
            if attempt == retries - 1:
                break
            time.sleep(base_delay * (2**attempt) + random.uniform(0, 1.0))
    raise RuntimeError(f"Google Trends request failed for {ticker} after {retries} attempts: {error}")


def fetch_trends(metadata: dict, tickers: Iterable[str], **kwargs) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        frames.append(fetch_ticker_trends(ticker, metadata[ticker].get("brand_keywords", []), **kwargs))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
