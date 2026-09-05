from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from commerce.domain import ProductSnapshot


_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(source, external_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_product_snapshots_identity_time
ON product_snapshots(source, external_id, observed_at);
"""


class SQLiteSnapshotRepository:
    """Small durable store for append-only observations.

    SQLite is intentionally only an infrastructure choice for v0.1. Domain and
    application layers depend on ``SnapshotRepository`` so PostgreSQL or a
    time-series store can replace it without changing the selection logic.
    """

    def __init__(self, path: str = "data/commerce.sqlite3") -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def save(self, snapshot: ProductSnapshot) -> None:
        payload = snapshot.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO product_snapshots
                    (source, external_id, observed_at, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot.source,
                    snapshot.external_id,
                    snapshot.observed_at.isoformat(),
                    payload,
                ),
            )
            conn.commit()

    def list_for_product(self, source: str, external_id: str) -> list[ProductSnapshot]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM product_snapshots
                WHERE source = ? AND external_id = ?
                ORDER BY observed_at ASC, id ASC
                """,
                (source, external_id),
            ).fetchall()
        return [ProductSnapshot.model_validate(json.loads(row["payload_json"])) for row in rows]
