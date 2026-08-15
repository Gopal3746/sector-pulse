# Validation Notes

Sector Pulse separates **pipeline correctness** from **economic interpretation**.

## Automated checks

- DuckDB schema initializes with primary keys for dimensions/facts.
- Price ingestion rejects negative prices/volume and inconsistent OHLC rows.
- STL decomposition is tested on a deterministic seasonal series.
- Rolling anomaly detection is tested against an injected residual spike.
- Pair-divergence transformation is covered by an offline unit test.
- GitHub Actions runs the unit tests and an offline demo pipeline on each push/PR.

## Live-source limitations

- Yahoo Finance access through `yfinance` is an open-source convenience layer and can be throttled or change behavior.
- Google Trends access through `pytrends` is unofficial, normalized to a relative 0–100 scale, and is cached/retried because requests may be rate-limited.
- SEC data is sourced from official EDGAR REST endpoints. A descriptive `SEC_USER_AGENT` is required before live SEC ingestion.
- An anomaly flag is a statistical screening signal, not a claim of causal relationship, investment alpha, or mispricing.

## Reproducible demo

The demo dataset is generated from deterministic synthetic series. `make demo` can persist it as `data/sample.duckdb`, while the dashboard can also build it in memory. Any sample finding should be described as illustrative, not empirical market evidence.
