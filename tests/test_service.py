"""Інтеграційні тести сервісного шару WorkbenchService без звернень до API."""

from __future__ import annotations

import pytest


def test_team_uses_kb_context_and_builds_unity_exports(service) -> None:
    events = []
    run = service.run_team(
        "JL-24: Додати PrismSplitter у Unity ECS з обмеженням max_bounces = 8 та NUnit тестами.",
        on_event=events.append,
    )
    assert run.task_key == "JL-24"
    assert "[Test]" in run.nunit_tests
    assert '"parMoves": 7' in run.preset_json
    assert run.result.state["kb_context"].startswith(("<fragment", "NOT_FOUND"))
    assert any(e["node"].startswith("retrieve_context") for e in events)
    assert service.history.get(run.run_id)["stop_reason"] == "approved"


def test_ask_returns_verified_obsidian_sources(service) -> None:
    answer = service.ask("Як працює розщеплення білого променя у призмі дисперсії?")
    labels = [s["label"] for s in answer.sources]
    assert answer.invalid_citations == []
    assert any(label.startswith("Призми дисперсії") for label in labels)
    assert answer.sources[0]["url"].startswith("obsidian://open?vault=kb-vault&file=")


def test_save_result_requires_reviewer_and_writes_inbox(service) -> None:
    run = service.run_team("JL-24: Реалізація PrismSplitter у Unity ECS та NUnit тестами.")
    with pytest.raises(ValueError):
        service.save_result(run, reviewer="   ")
    path = service.save_result(run, reviewer="Світенко")
    assert path.parent.name == "Inbox"
    text = path.read_text(encoding="utf-8")
    assert 'approved_by: "Світенко"' in text
    assert service.history.get(run.run_id)["saved_path"] == str(path)
