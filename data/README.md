# Data directory

`warehouse.duckdb` is the live local warehouse and is gitignored.

`sample.duckdb` is generated with `make demo`. The Streamlit app does not require the file to be committed: if it is absent, the app builds the same deterministic demo dataset in an in-memory DuckDB database at startup.

Raw Google Trends cache files are written under `data/raw/trends/` and are gitignored.
