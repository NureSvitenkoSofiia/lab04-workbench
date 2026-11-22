"""System Usability Scale (Brooke, 1996): обчислення оцінки 0..100 з CSV.

Запуск: uv run python -m eval.sus eval/sus_example.csv
"""

from __future__ import annotations

import csv
import statistics
import sys


def sus_score(answers: list[int]) -> float:
    """Непарні (індекс 0,2,...) позитивні (a - 1), парні негативні (5 - a)."""
    if len(answers) != 10 or not all(1 <= a <= 5 for a in answers):
        raise ValueError("SUS потребує 10 відповідей у діапазоні 1..5")
    total = sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))
    return total * 2.5


def main(path: str) -> None:
    scores = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            score = sus_score([int(row[f"q{i}"]) for i in range(1, 11)])
            scores.append(score)
            print(f"{row['respondent']}: {score:.1f}")
    print(f"\nSUS mean = {statistics.mean(scores):.1f}, n = {len(scores)}")


if __name__ == "__main__":
    main(sys.argv[1])
