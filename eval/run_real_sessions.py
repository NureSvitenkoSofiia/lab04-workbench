"""Скрипт виконання 10 реальних сесій робочого місця JarLight (5 ask + 5 team)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from workbench.service import build_service

ASK_QUESTIONS = [
    "Які калібри скляних банок реалізовано у грі JarLight та яка їхня місткість?",
    "Чим поворотні дзеркала mirror_element відрізняються від призм дисперсії?",
    "Як працює адитивне змішування RGB-спектру та умови розквіту кристалів?",
    "Які обмеження продуктивності діють у Burst/ECS конвеєрі променевого трасування?",
    "Як працюють таймери розчинення банок і події в шині EventBus?",
]

TEAM_TASKS = [
    "JL-24: Реалізувати елемент PrismSplitter у Unity ECS/Burst: розщеплення білого променя на R, G, B під кутом 60 град., ліміт max_bounces=8, JSON-пресет рівня (Par Moves <= 7) та NUnit тести.",
    "JL-27: Додати поворотне дзеркало MirrorElement45 у Unity ECS із дискретними кутами 45/90 град., детектором циклу відбиттів (max_bounces <= 12) та NUnit тестами.",
    "JL-29: Додати в JarLight якийсь крутий бонус для кристалів і приємні ефекти якомога швидше.",
    "JL-31: Реалізувати таймер розчинення скляних банок (jar_small=3 ходи, jar_medium=5 ходів) із подією JarDissolvedEvent в EventBus та NUnit тестами.",
    "JL-35: Додати багатобарвну кристалічну квітку (адитивне змішування R+G+B або Yellow=R+G) із перевіркою умови перемоги, JSON-пресетом і NUnit тестами.",
]


def main() -> None:
    svc = build_service()
    details = []

    for q in ASK_QUESTIONS:
        ans = svc.ask(q)
        ok = bool(ans.sources) and not ans.invalid_citations
        svc.rate(ans.run_id, ok)
        details.append(
            {
                "kind": "ask",
                "run_id": ans.run_id,
                "sources": [s["label"] for s in ans.sources],
                "invalid_citations": ans.invalid_citations,
                "rated": int(ok),
            }
        )
        print("ASK:", ans.run_id, "sources=", len(ans.sources), "invalid=", ans.invalid_citations)

    for t in TEAM_TASKS:
        run = svc.run_team(t)
        ok = run.stop_reason in {"approved", "max_drafts", "needs_clarification"}
        svc.rate(run.run_id, ok)
        details.append(
            {
                "kind": "team",
                "run_id": run.run_id,
                "task_key": run.task_key,
                "stop_reason": run.stop_reason,
                "drafts": run.result.state.get("drafts", 0),
                "has_nunit": bool(run.nunit_tests),
                "has_json": bool(run.preset_json),
                "rated": int(ok),
            }
        )
        print("TEAM:", run.run_id, run.task_key, run.stop_reason, "nunit=", bool(run.nunit_tests))

    rows = svc.history.list(limit=10)
    summary = svc.history.summary()

    out_csv = Path("eval/real_runs.csv")
    if rows:
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    Path("eval/real_summary.json").write_text(
        json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("SUMMARY:", summary)


if __name__ == "__main__":
    main()
