"""SQLite-сховище історії запусків робочого місця розробника JarLight."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

CREATE_RUNS_SQL = """
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

LIST_COLUMNS = (
    "id, kind, created, input, llm_calls, tokens, seconds, "
    "stop_reason, rating, saved_path"
)

SUMMARY_SQL = """
SELECT
    COUNT(*) AS runs,
    AVG(llm_calls) AS avg_calls,
    AVG(seconds) AS avg_seconds,
    SUM(tokens) AS tokens,
    AVG(rating) AS positive_share,
    SUM(saved_path IS NOT NULL) AS saved
FROM runs
"""


class HistoryStore:
    """Персистентний журнал запусків БЗ і команди агентів у SQLite."""

    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._execute(CREATE_RUNS_SQL)

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with closing(self._open()) as conn:
            with conn:
                conn.execute(sql, params)

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict | None:
        with closing(self._open()) as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row is not None else None

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict]:
        with closing(self._open()) as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(item) for item in rows]

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
        """Реєструє новий запуск у таблиці runs і повертає його короткий ідентифікатор."""
        entry_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(details or {}, ensure_ascii=False)
        self._execute(
            "INSERT INTO runs "
            "(id, kind, created, input, output, llm_calls, tokens, seconds, stop_reason, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                kind,
                timestamp,
                input_text,
                output,
                llm_calls,
                tokens,
                seconds,
                stop_reason,
                payload,
            ),
        )
        return entry_id

    def rate(self, run_id: str, rating: int) -> None:
        """Зберігає бінарну оцінку якості (0 або 1) для вибраного запуску."""
        self._execute("UPDATE runs SET rating = ? WHERE id = ?", (rating, run_id))

    def mark_saved(self, run_id: str, path: str) -> None:
        """Фіксує шлях збереженої нотатки Obsidian після підтвердження рецензентом."""
        self._execute("UPDATE runs SET saved_path = ? WHERE id = ?", (path, run_id))

    def get(self, run_id: str) -> dict | None:
        """Повертає повний запис запуску за ідентифікатором або None."""
        return self._fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))

    def list(self, limit: int = 100, kind: str | None = None) -> list[dict]:
        """Повертає останні записи журналу (за потреби з фільтром за типом ask/team)."""
        if kind in {"ask", "team"}:
            return self._fetch_all(
                f"SELECT {LIST_COLUMNS} FROM runs WHERE kind = ? "
                "ORDER BY created DESC LIMIT ?",
                (kind, limit),
            )
        return self._fetch_all(
            f"SELECT {LIST_COLUMNS} FROM runs ORDER BY created DESC LIMIT ?",
            (limit,),
        )

    def summary(self) -> dict:
        """Обчислює агреговані метрики якості та витрат за всією історією."""
        return self._fetch_one(SUMMARY_SQL) or {}
