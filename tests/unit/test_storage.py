"""Модульні тести SQLite журналу HistoryStore."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from workbench.storage import HistoryStore


def test_history_store_crud_and_summary(tmp_path: Path) -> None:
    st = HistoryStore(tmp_path / "test.db")
    r1 = st.add("ask", "Q1", "A1", 2, 500, 1.5)
    r2 = st.add("team", "JL-24", "Report", 5, 2500, 12.0, stop_reason="approved")
    st.rate(r1, 1)
    st.rate(r2, 0)
    st.mark_saved(r2, "Inbox/jl24.md")

    summary = st.summary()
    assert summary["runs"] == 2
    assert summary["tokens"] == 3000
    assert summary["positive_share"] == pytest.approx(0.5)
    assert summary["saved"] == 1


def test_history_store_enforces_check_constraints(tmp_path: Path) -> None:
    st = HistoryStore(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        st.add("invalid_kind", "Q", "A", 1, 10, 0.1)
    rid = st.add("ask", "Q", "A", 1, 10, 0.1)
    with pytest.raises(sqlite3.IntegrityError):
        st.rate(rid, 5)
