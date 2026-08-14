from __future__ import annotations

from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS dim_ticker (
    ticker VARCHAR PRIMARY KEY,
    company_name VARCHAR,
    subsector VARCHAR,
    brand_keywords VARCHAR[]
);

CREATE TABLE IF NOT EXISTS fact_price (
    ticker VARCHAR,
    date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS fact_trends (
    ticker VARCHAR,
    keyword VARCHAR,
    date DATE,
    interest_score DOUBLE,
    PRIMARY KEY (ticker, keyword, date)
);

CREATE TABLE IF NOT EXISTS fact_filings (
    ticker VARCHAR,
    accession_number VARCHAR PRIMARY KEY,
    filing_type VARCHAR,
    filing_date DATE,
    period_end DATE
);

CREATE TABLE IF NOT EXISTS fact_financials (
    ticker VARCHAR,
    tag VARCHAR,
    period_end DATE,
    value DOUBLE,
    filed_date DATE,
    PRIMARY KEY (ticker, tag, period_end)
);

CREATE TABLE IF NOT EXISTS fact_seasonality (
    ticker VARCHAR,
    metric VARCHAR,
    date DATE,
    value DOUBLE,
    trend DOUBLE,
    seasonal DOUBLE,
    residual DOUBLE,
    PRIMARY KEY (ticker, metric, date)
);

CREATE TABLE IF NOT EXISTS fact_anomaly (
    ticker VARCHAR,
    metric VARCHAR,
    date DATE,
    value DOUBLE,
    z_score DOUBLE,
    flagged BOOLEAN,
    description VARCHAR,
    PRIMARY KEY (ticker, metric, date)
);

CREATE TABLE IF NOT EXISTS fact_pair_divergence (
    pair VARCHAR,
    ticker_a VARCHAR,
    ticker_b VARCHAR,
    date DATE,
    return_a DOUBLE,
    return_b DOUBLE,
    divergence DOUBLE,
    z_score DOUBLE,
    flagged BOOLEAN,
    PRIMARY KEY (pair, date)
);
"""

TABLE_COLUMNS = {
    "dim_ticker": ["ticker", "company_name", "subsector", "brand_keywords"],
    "fact_price": ["ticker", "date", "open", "high", "low", "close", "volume"],
    "fact_trends": ["ticker", "keyword", "date", "interest_score"],
    "fact_filings": ["ticker", "accession_number", "filing_type", "filing_date", "period_end"],
    "fact_financials": ["ticker", "tag", "period_end", "value", "filed_date"],
    "fact_seasonality": ["ticker", "metric", "date", "value", "trend", "seasonal", "residual"],
    "fact_anomaly": ["ticker", "metric", "date", "value", "z_score", "flagged", "description"],
    "fact_pair_divergence": ["pair", "ticker_a", "ticker_b", "date", "return_a", "return_b", "divergence", "z_score", "flagged"],
}


def connect(path: str | Path = "data/warehouse.duckdb", read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def init_db(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(SCHEMA_SQL)


def table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    rows = conn.execute("SHOW TABLES").fetchall()
    return {row[0] for row in rows}


def upsert_dataframe(conn: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    if table not in TABLE_COLUMNS:
        raise ValueError(f"Unsupported table: {table}")

    columns = TABLE_COLUMNS[table]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns for {table}: {missing}")

    clean = frame[columns].copy()
    conn.register("_incoming", clean)
    try:
        conn.execute(f"INSERT OR REPLACE INTO {table} BY NAME SELECT * FROM _incoming")
    finally:
        conn.unregister("_incoming")
    return len(clean)


def load_ticker_dimension(conn: duckdb.DuckDBPyConnection, metadata: dict) -> int:
    rows = [
        {
            "ticker": ticker,
            "company_name": details["company_name"],
            "subsector": details["subsector"],
            "brand_keywords": details.get("brand_keywords", []),
        }
        for ticker, details in metadata.items()
    ]
    return upsert_dataframe(conn, "dim_ticker", pd.DataFrame(rows))


def row_counts(conn: duckdb.DuckDBPyConnection, tables: Iterable[str] | None = None) -> dict[str, int]:
    tables = list(tables or TABLE_COLUMNS)
    return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
