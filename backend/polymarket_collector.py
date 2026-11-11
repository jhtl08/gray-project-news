"""Collect active Polymarket markets from the Gamma API.

Fetches active, non-closed markets for a set of priority tags plus markets
flagged ``new=true``, dedupes by market id, and writes a JSON snapshot under
``backend/polymarket_data/``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://gamma-api.polymarket.com"

# Polymarket tag ids that are prioritized for collection.
PRIORITY_TAG_IDS: list[int] = [2, 100328, 120, 107]

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "polymarket_data"


def _request_markets(params: dict[str, Any]) -> list[dict[str, Any]]:
    response = requests.get(f"{BASE_URL}/markets", params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("unexpected Polymarket response: expected a list of markets")
    return data


def collect_markets(directory: Path | str | None = None) -> dict[str, Any]:
    """Collect active markets and return the payload.

    Markets are fetched per priority tag (paginated, up to 100 per page) and
    again for ``new=true`` markets. Results are deduped by market id. A
    snapshot is written to ``<directory>/<UTC timestamp>.json`` unless
    ``directory`` is falsy (pass ``None`` for the default directory).
    """
    target_dir = Path(directory) if directory is not None else DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    markets_by_id: dict[str, dict[str, Any]] = {}

    def add_batch(batch: list[dict[str, Any]]) -> None:
        for market in batch:
            market_id = market.get("id")
            if market_id is None:
                continue
            markets_by_id[str(market_id)] = market

    # Priority tags.
    for tag_id in PRIORITY_TAG_IDS:
        offset = 0
        while True:
            batch = _request_markets(
                {
                    "active": "true",
                    "closed": "false",
                    "tag_id": tag_id,
                    "limit": 100,
                    "offset": offset,
                }
            )
            add_batch(batch)
            if len(batch) < 100:
                break
            offset += 100

    # Newly created markets.
    offset = 0
    while True:
        batch = _request_markets(
            {
                "active": "true",
                "closed": "false",
                "new": "true",
                "limit": 100,
                "offset": offset,
            }
        )
        add_batch(batch)
        if len(batch) < 100:
            break
        offset += 100

    collected_at = datetime.now(timezone.utc).isoformat()
    markets = list(markets_by_id.values())
    payload: dict[str, Any] = {
        "source": "polymarket",
        "collected_at": collected_at,
        "markets": markets,
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = target_dir / f"{timestamp}.json"
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    return payload


def main() -> None:
    payload = collect_markets()
    print(f"Collected {len(payload['markets'])} markets")


if __name__ == "__main__":
    main()