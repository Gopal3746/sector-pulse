.PHONY: install demo live dashboard test verify clean

install:
	python -m pip install -r requirements.txt

demo:
	python -m src.run_pipeline --mode demo --db data/sample.duckdb

live:
	python -m src.run_pipeline --mode live --db data/warehouse.duckdb

dashboard:
	SECTOR_PULSE_DB=data/sample.duckdb streamlit run dashboard/app.py

test:
	pytest -q

verify: test
	PYTHONPATH=. python scripts/verify_project.py

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
