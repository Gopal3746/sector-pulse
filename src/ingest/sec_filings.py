from __future__ import annotations

import os
import time
from typing import Iterable

import pandas as pd
import requests

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

CANONICAL_TAGS = {
    "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "CostOfGoodsSold": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
    "InventoryNet": ["InventoryNet"],
}


def sec_headers(user_agent: str | None = None) -> dict[str, str]:
    user_agent = user_agent or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise ValueError("Set SEC_USER_AGENT to a descriptive value such as 'SectorPulse your_email@example.com'.")
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def _get_json(url: str, headers: dict[str, str], session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def cik_lookup(tickers: Iterable[str], user_agent: str | None = None) -> dict[str, int]:
    headers = sec_headers(user_agent)
    payload = _get_json(SEC_TICKERS_URL, headers)
    wanted = {t.upper() for t in tickers}
    mapping = {}
    for row in payload.values():
        ticker = str(row["ticker"]).upper()
        if ticker in wanted:
            mapping[ticker] = int(row["cik_str"])
    missing = wanted - mapping.keys()
    if missing:
        raise KeyError(f"SEC CIK lookup failed for: {sorted(missing)}")
    return mapping


def normalize_filings(ticker: str, payload: dict) -> pd.DataFrame:
    recent = payload.get("filings", {}).get("recent", {})
    fields = ["accessionNumber", "form", "filingDate", "reportDate"]
    if not recent or not all(field in recent for field in fields):
        return pd.DataFrame(columns=["ticker", "accession_number", "filing_type", "filing_date", "period_end"])
    frame = pd.DataFrame({field: recent[field] for field in fields})
    frame = frame[frame["form"].isin(["10-Q", "10-K", "8-K"])].copy()
    frame["ticker"] = ticker
    frame = frame.rename(columns={"accessionNumber": "accession_number", "form": "filing_type", "filingDate": "filing_date", "reportDate": "period_end"})
    frame["filing_date"] = pd.to_datetime(frame["filing_date"], errors="coerce").dt.date
    frame["period_end"] = pd.to_datetime(frame["period_end"], errors="coerce").dt.date
    return frame[["ticker", "accession_number", "filing_type", "filing_date", "period_end"]].dropna(subset=["filing_date"])


def _best_tag(facts: dict, aliases: list[str]) -> tuple[str, dict] | None:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for alias in aliases:
        if alias in us_gaap:
            return alias, us_gaap[alias]
    return None


def normalize_financials(ticker: str, payload: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for canonical, aliases in CANONICAL_TAGS.items():
        match = _best_tag(payload, aliases)
        if not match:
            continue
        _, fact = match
        units = fact.get("units", {}).get("USD", [])
        framed = [unit for unit in units if unit.get("frame")]
        if framed:
            units = framed
        for unit in units:
            if unit.get("form") not in {"10-Q", "10-K"}:
                continue
            if not unit.get("end") or unit.get("val") is None or not unit.get("filed"):
                continue
            rows.append({
                "ticker": ticker,
                "tag": canonical,
                "period_end": pd.to_datetime(unit["end"]).date(),
                "value": float(unit["val"]),
                "filed_date": pd.to_datetime(unit["filed"]).date(),
            })
    if not rows:
        return pd.DataFrame(columns=["ticker", "tag", "period_end", "value", "filed_date"])
    frame = pd.DataFrame(rows).sort_values("filed_date")
    return frame.drop_duplicates(["ticker", "tag", "period_end"], keep="last")


def fetch_sec_data(tickers: Iterable[str], user_agent: str | None = None, delay: float = 0.12) -> tuple[pd.DataFrame, pd.DataFrame]:
    tickers = [ticker.upper() for ticker in tickers]
    headers = sec_headers(user_agent)
    ciks = cik_lookup(tickers, user_agent)
    filings, financials = [], []
    session = requests.Session()
    for ticker in tickers:
        cik = f"{ciks[ticker]:010d}"
        submissions = _get_json(SEC_SUBMISSIONS_URL.format(cik=cik), headers, session)
        filings.append(normalize_filings(ticker, submissions))
        time.sleep(delay)
        facts = _get_json(SEC_COMPANYFACTS_URL.format(cik=cik), headers, session)
        financials.append(normalize_financials(ticker, facts))
        time.sleep(delay)
    return (
        pd.concat(filings, ignore_index=True) if filings else pd.DataFrame(),
        pd.concat(financials, ignore_index=True) if financials else pd.DataFrame(),
    )
