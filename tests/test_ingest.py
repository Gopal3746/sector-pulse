import pandas as pd

from src.ingest.prices import normalize_history, validate_prices
from src.ingest.sec_filings import normalize_financials


def test_price_normalization_and_validation():
    raw = pd.DataFrame({
        "Open": [10.0, 10.5],
        "High": [11.0, 11.2],
        "Low": [9.8, 10.2],
        "Close": [10.7, 10.9],
        "Volume": [1000, 1200],
    }, index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    raw.index.name = "Date"
    frame = normalize_history("TST", raw)
    result = validate_prices(frame)
    assert result.valid
    assert frame.iloc[0]["ticker"] == "TST"


def test_negative_price_fails_validation():
    frame = pd.DataFrame({
        "ticker": ["TST"], "date": [pd.Timestamp("2026-01-02").date()],
        "open": [-1.0], "high": [2.0], "low": [-2.0], "close": [1.0], "volume": [10]
    })
    assert not validate_prices(frame).valid


def test_sec_financial_normalization_uses_canonical_tags():
    payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"end": "2026-03-31", "val": 100.0, "filed": "2026-05-01", "form": "10-Q"}
    ]}}}}}
    frame = normalize_financials("TST", payload)
    assert frame.iloc[0]["tag"] == "Revenue"
    assert frame.iloc[0]["value"] == 100.0
