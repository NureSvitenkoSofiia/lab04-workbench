"""Прикладний сервісний фасад робочого місця JarLight (ізольований від UI)."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

from .exporters import (
    save_to_vault,
    to_draft_pr_md,
    to_level_preset_json,
    to_unity_nunit_tests,
    to_vault_note,
)
from .runner import OnEvent, RunResult, run_agent
from .storage import HistoryStore

_SOURCE_TAG_PATTERN = re.compile(r'source="\[\[([^\]]+)\]\]" path="([^"]+)"')
_WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def _extract_verified_sources(
    tool_outputs: list[str],
    url_builder: Callable[[str], str],
) -> tuple[dict[str, str], list[dict]]:
    """Витягує підтверджені теги source з фактичних відповідей інструментів БЗ."""
    path_by_label: dict[str, str] = {}
    for raw_output in tool_outputs:
        for label, rel_path in _SOURCE_TAG_PATTERN.findall(raw_output):
            path_by_label[label] = rel_path

    records = [
        {"label": label, "path": rel_path, "url": url_builder(rel_path)}
        for label, rel_path in path_by_label.items()
    ]
    return path_by_label, records


def _find_invalid_citations(answer_text: str, verified_labels: set[str]) -> list[str]:
    """Знаходить згадки [[...]] у відповіді моделі, яких не було у виводах інструментів."""
    verified_notes = {item.split("#")[0] for item in verified_labels}
    unverified: set[str] = set()
    for citation in _WIKILINK_PATTERN.findall(answer_text):
        base_note = citation.split("#")[0]
        if citation not in verified_labels and base_note not in verified_notes:
            unverified.add(citation)
    return sorted(unverified)


def _resolve_team_metadata(state: dict, fallback_text: str) -> tuple[str, str, str, str]:
    """Визначає ключ GDD-задачі, заголовок, статус завершення та текст звіту."""
    plan = state.get("plan") or {}
    pr_draft = state.get("pr_draft") or {}

    task_key = str(
        pr_draft.get("task_key")
        or plan.get("task_key")
        or state.get("task_key")
        or "JL-NEW"
    )
    title = str(plan.get("title") or pr_draft.get("pr_title") or "JarLight Feature")
    stop_reason = str(state.get("stop_reason") or "completed")
    report = str(state.get("report") or fallback_text)
    return task_key, title, stop_reason, report


@dataclass
class Answer:
    """Відповідь БЗ-асистента JarLight із верифікованими посиланнями Obsidian."""

    run_id: str
    text: str
    sources: list[dict]
    invalid_citations: list[str]
    result: RunResult

    @property
    def linked_text(self) -> str:
        """Перетворює підтверджені wikilink-цитати на клікабельні URI obsidian://."""
        uri_map = {entry["label"]: entry["url"] for entry in self.sources}

        def _replace(match: re.Match[str]) -> str:
            label = match.group(1)
            uri = uri_map.get(label)
            return f"[{label}]({uri})" if uri else match.group(0)

        return _WIKILINK_PATTERN.sub(_replace, self.text)


@dataclass
class TeamRun:
    """Пакет результатів виконання МАС-конвеєра конструювання JarLight."""

    run_id: str
    task_key: str
    title: str
    report: str
    pr_md: str
    nunit_tests: str
    preset_json: str
    stop_reason: str
    result: RunResult


class WorkbenchService:
    """Сервісний фасад сценаріїв UC1-UC5 для робочого місця розробника JarLight."""

    def __init__(
        self,
        team_agent,
        kb_agent,
        history: HistoryStore,
        vault: Path | None = None,
        vault_name: str = "",
    ):
        self.team_agent = team_agent
        self.kb_agent = kb_agent
        self.history = history
        self.vault = vault
        self.vault_name = vault_name

    def obsidian_url(self, path: str) -> str:
        """Формує локальний URI для відкриття нотатки в настільному Obsidian."""
        return f"obsidian://open?vault={quote(self.vault_name)}&file={quote(path)}"

    def ask(self, question: str, on_event: OnEvent | None = None) -> Answer:
        """UC1: Виконує запит до БЗ та перевіряє достовірність цитованих джерел."""
        run_res = run_agent(self.kb_agent, question, on_event=on_event)
        path_map, sources = _extract_verified_sources(
            run_res.tool_outputs,
            self.obsidian_url,
        )
        invalid = _find_invalid_citations(run_res.final_text, set(path_map))
        total_calls = sum(run_res.llm_calls.values())

        run_id = self.history.add(
            kind="ask",
            input_text=question,
            output=run_res.final_text,
            llm_calls=total_calls,
            tokens=run_res.tokens,
            seconds=run_res.seconds,
            details={"sources": list(path_map), "invalid": invalid},
        )
        return Answer(
            run_id=run_id,
            text=run_res.final_text,
            sources=sources,
            invalid_citations=invalid,
            result=run_res,
        )

    def run_team(self, request: str, on_event: OnEvent | None = None) -> TeamRun:
        """UC2/UC3: Запускає граф МАС JarLight і готує артефакти для Unity/QA."""
        run_res = run_agent(self.team_agent, request, on_event=on_event)
        state = run_res.state
        task_key, title, stop_reason, report = _resolve_team_metadata(
            state,
            run_res.final_text,
        )

        pr_md = to_draft_pr_md(state, fallback_report=report)
        nunit_tests = to_unity_nunit_tests(state)
        preset_json = to_level_preset_json(state)
        total_calls = sum(run_res.llm_calls.values())

        run_id = self.history.add(
            kind="team",
            input_text=request,
            output=report,
            llm_calls=total_calls,
            tokens=run_res.tokens,
            seconds=run_res.seconds,
            stop_reason=stop_reason,
            details={
                "task_key": task_key,
                "drafts": state.get("drafts", 0),
                "llm_calls": run_res.llm_calls,
            },
        )
        return TeamRun(
            run_id=run_id,
            task_key=task_key,
            title=title,
            report=report,
            pr_md=pr_md,
            nunit_tests=nunit_tests,
            preset_json=preset_json,
            stop_reason=stop_reason,
            result=run_res,
        )

    def save_result(self, run: TeamRun, reviewer: str) -> Path:
        """UC4 (Human-in-the-loop): записує схвалений рецензентом результат у Inbox/."""
        if not self.vault:
            raise RuntimeError("Сховище Obsidian не налаштовано")

        author = reviewer.strip()
        if not author:
            raise ValueError("Потрібно вказати ім'я рецензента")

        note_body = to_vault_note(
            task_key=run.task_key,
            title=run.title,
            report=run.pr_md or run.report,
            run_id=run.run_id,
            reviewer=author,
        )
        saved_path = save_to_vault(
            self.vault,
            note_body,
            f"{run.task_key} {run.title}",
            folder="Inbox",
        )
        self.history.mark_saved(run.run_id, str(saved_path))
        return saved_path

    def rate(self, run_id: str, positive: bool) -> None:
        """UC5: Записує користувацьку оцінку запуску в SQLite."""
        self.history.rate(run_id, int(positive))


def build_service() -> WorkbenchService:
    """Фабрика сервісу робочого місця з конфігурацією із .env."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from app.agent import build_workflow, gemini
    from app.kb_assistant import build_kb_assistant
    from kb.tools import build_tools

    kb_tools = build_tools()
    workflow = build_workflow(
        gemini(),
        kb_search=lambda query: kb_tools.search_knowledge(query, skip_inbox=True),
        use_kb_agent=False,
    )
    kb_agent = build_kb_assistant(gemini(), kb_tools)
    history = HistoryStore(os.getenv("WORKBENCH_DB", "workbench.db"))
    vault_name = os.getenv("OBSIDIAN_VAULT_NAME", kb_tools.vault.name)
    return WorkbenchService(workflow, kb_agent, history, kb_tools.vault, vault_name)
