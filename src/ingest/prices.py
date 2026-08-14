from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass
class ValidationResult:
    valid: bool
    warnings: list[str]


def normalize_history(ticker: str, history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume"])

    frame = history.copy().reset_index()
    date_col = "Date" if "Date" in frame.columns else frame.columns[0]
    rename = {date_col: "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    frame = frame.rename(columns=rename)
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"Price history is missing columns: {missing}")
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_convert(None).dt.date
    frame.insert(0, "ticker", ticker.upper())
    return frame[["ticker", *required]].dropna(subset=["date", "close"])


def validate_prices(frame: pd.DataFrame) -> ValidationResult:
    warnings: list[str] = []
    if frame.empty:
        return ValidationResult(False, ["No price rows returned."])

    price_cols = ["open", "high", "low", "close"]
    if (frame[price_cols] < 0).any().any():
        return ValidationResult(False, ["Negative price values detected."])
    if (frame["volume"] < 0).any():
        return ValidationResult(False, ["Negative volume values detected."])
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        return ValidationResult(False, ["OHLC consistency check failed: high below another price field."])
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        return ValidationResult(False, ["OHLC consistency check failed: low above another price field."])

    ordered = pd.to_datetime(frame["date"]).sort_values()
    if len(ordered) > 1:
        max_gap = ordered.diff().dropna().dt.days.max()
        if pd.notna(max_gap) and max_gap > 7:
            warnings.append(f"Largest calendar gap is {int(max_gap)} days; review for suspension/data outage.")
    return ValidationResult(True, warnings)


def fetch_prices(tickers: Iterable[str], period: str = "2y") -> tuple[pd.DataFrame, dict[str, list[str]]]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is required for live price ingestion. Install requirements.txt.") from exc

    frames: list[pd.DataFrame] = []
    warnings: dict[str, list[str]] = {}
    for ticker in tickers:
        history = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        normalized = normalize_history(ticker, history)
        result = validate_prices(normalized)
        if not result.valid:
            raise ValueError(f"{ticker}: {'; '.join(result.warnings)}")
        if result.warnings:
            warnings[ticker] = result.warnings
        frames.append(normalized)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(), warnings
