from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", "config/tickers.yaml", "src/db.py", "src/run_pipeline.py",
    "src/ingest/prices.py", "src/ingest/trends.py", "src/ingest/sec_filings.py",
    "src/transform/seasonality.py", "src/transform/anomaly.py", "dashboard/app.py",
    "tests/test_db.py", ".github/workflows/ci.yml", "data/README.md",
]

missing = [path for path in REQUIRED if not (ROOT / path).exists()]
if missing:
    raise SystemExit(f"Missing required project files: {missing}")

from src.demo import build_demo
conn = duckdb.connect(":memory:")
build_demo(conn, ["HD", "LOW", "DG", "DLTR"])
counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ["dim_ticker", "fact_price", "fact_trends", "fact_anomaly"]}
if min(counts.values()) <= 0:
    raise SystemExit(f"Demo build has empty core tables: {counts}")
print("project validation passed", counts)
