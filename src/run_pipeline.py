from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.config import configured_pairs, ticker_metadata
from src.db import connect, init_db, load_ticker_dimension, row_counts, upsert_dataframe
from src.demo import build_demo
from src.ingest.prices import fetch_prices
from src.ingest.sec_filings import fetch_sec_data
from src.ingest.trends import fetch_trends
from src.transform.anomaly import detect_anomalies
from src.transform.divergence import pair_divergence
from src.transform.seasonality import build_seasonality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sector Pulse retail alt-data pipeline")
    parser.add_argument("--mode", choices=["demo", "live"], default="demo")
    parser.add_argument("--db", default="data/warehouse.duckdb")
    parser.add_argument("--tickers", nargs="*", help="Optional subset of configured tickers")
    parser.add_argument("--period", default="2y", help="yfinance period for live price history")
    parser.add_argument("--skip-trends", action="store_true")
    parser.add_argument("--skip-sec", action="store_true")
    parser.add_argument("--force-trends", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = ticker_metadata()
    tickers = [ticker.upper() for ticker in (args.tickers or list(metadata))]
    unknown = [ticker for ticker in tickers if ticker not in metadata]
    if unknown:
        raise SystemExit(f"Unknown configured tickers: {unknown}")

    conn = connect(args.db)
    init_db(conn)
    load_ticker_dimension(conn, {ticker: metadata[ticker] for ticker in tickers})

    if args.mode == "demo":
        inserted = build_demo(conn, tickers)
        print("Demo pipeline complete:", inserted)
        print("Row counts:", row_counts(conn))
        return

    prices, warnings = fetch_prices(tickers, args.period)
    upsert_dataframe(conn, "fact_price", prices)
    for ticker, messages in warnings.items():
        for message in messages:
            print(f"WARNING {ticker}: {message}")

    if args.skip_trends:
        placeholders = ",".join("?" for _ in tickers)
        trends = conn.execute(f"SELECT * FROM fact_trends WHERE ticker IN ({placeholders})", tickers).df()
    else:
        try:
            trends = fetch_trends(metadata, tickers, force=args.force_trends)
            upsert_dataframe(conn, "fact_trends", trends)
        except RuntimeError as exc:
            print(f"WARNING: {exc}")
            print("WARNING: continuing with cached trend rows if available; use --skip-trends to suppress live Trends calls.")
            placeholders = ",".join("?" for _ in tickers)
            trends = conn.execute(f"SELECT * FROM fact_trends WHERE ticker IN ({placeholders})", tickers).df()

    if not args.skip_sec:
        filings, financials = fetch_sec_data(tickers, os.getenv("SEC_USER_AGENT"))
        upsert_dataframe(conn, "fact_filings", filings)
        upsert_dataframe(conn, "fact_financials", financials)

    seasonality = build_seasonality(prices, trends)
    upsert_dataframe(conn, "fact_seasonality", seasonality)
    anomalies = detect_anomalies(seasonality)
    upsert_dataframe(conn, "fact_anomaly", anomalies)
    pairs = [pair for pair in configured_pairs() if pair[0] in tickers and pair[1] in tickers]
    upsert_dataframe(conn, "fact_pair_divergence", pair_divergence(prices, pairs))
    print("Live pipeline complete.")
    print("Row counts:", row_counts(conn))


if __name__ == "__main__":
    main()
