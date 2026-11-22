"""Журнал запусків у SQLite (workbench.db) для метрик якості і вартості."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('ask', 'team')),
    created TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT,
    llm_calls INTEGER,
    tokens INTEGER,
    seconds REAL,
    stop_reason TEXT,
    rating INTEGER CHECK (rating IN (0, 1)),
    saved_path TEXT,
    details TEXT
)
"""


class HistoryStore:
    """Сховище експлуатаційних метрик та користувацьких оцінок у SQLite."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        with self._connect() as db:
            db.execute(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def add(
        self,
        kind: str,
        input_text: str,
        output: str,
        llm_calls: int,
        tokens: int,
        seconds: float,
        stop_reason: str = "",
        details: dict | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs (id, kind, created, input, output, llm_calls, tokens, "
                "seconds, stop_reason, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    kind,
                    datetime.now().isoformat(timespec="seconds"),
                    input_text,
                    output,
                    llm_calls,
                    tokens,
                    seconds,
                    stop_reason,
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )
        return run_id

    def rate(self, run_id: str, rating: int) -> None:
        with self._connect() as db:
            db.execute("UPDATE runs SET rating = ? WHERE id = ?", (rating, run_id))

    def mark_saved(self, run_id: str, path: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE runs SET saved_path = ? WHERE id = ?", (path, run_id))

    def get(self, run_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, kind, created, input, llm_calls, tokens, seconds, "
                "stop_reason, rating, saved_path FROM runs "
                "ORDER BY created DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def summary(self) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS runs, AVG(llm_calls) AS avg_calls, "
                "AVG(seconds) AS avg_seconds, SUM(tokens) AS tokens, "
                "AVG(rating) AS positive_share, "
                "SUM(saved_path IS NOT NULL) AS saved FROM runs"
            ).fetchone()
        return dict(row)
