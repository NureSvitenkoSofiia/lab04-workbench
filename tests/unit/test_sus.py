"""Модульний тест обчислення SUS (Brooke, 1996)."""

from __future__ import annotations

import pytest

from eval.sus import sus_score


def test_sus_score_formula() -> None:
    assert sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == pytest.approx(75.0)
    assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == pytest.approx(100.0)
    with pytest.raises(ValueError):
        sus_score([3, 3])
