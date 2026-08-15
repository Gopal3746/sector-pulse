from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "tickers.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not data or "tickers" not in data:
        raise ValueError("Ticker config must contain a top-level 'tickers' mapping.")
    return data


def ticker_metadata(path: str | Path = DEFAULT_CONFIG) -> dict[str, dict[str, Any]]:
    return load_config(path)["tickers"]


def configured_pairs(path: str | Path = DEFAULT_CONFIG) -> list[tuple[str, str]]:
    return [tuple(pair) for pair in load_config(path).get("pairs", [])]
