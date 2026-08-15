from src.db import connect, init_db, table_names


def test_schema_initializes(tmp_path):
    conn = connect(tmp_path / "test.duckdb")
    init_db(conn)
    expected = {"dim_ticker", "fact_price", "fact_trends", "fact_filings", "fact_financials", "fact_seasonality", "fact_anomaly", "fact_pair_divergence"}
    assert expected.issubset(table_names(conn))
