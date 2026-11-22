"""Сервісний шар робочого місця розробника Unity JarLight (відокремлений від UI)."""

from __future__ import annotations

import os
import re
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

SOURCE_RE = re.compile(r'source="\[\[([^\]]+)\]\]" path="([^"]+)"')
CITATION_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class Answer:
    """Відповідь асистента бази знань JarLight із перевіреними посиланнями Obsidian."""

    run_id: str
    text: str
    sources: list[dict]
    invalid_citations: list[str]
    result: RunResult

    @property
    def linked_text(self) -> str:
        """Замінює підтверджені [[Нотатка#Розділ]] на клікабельні URI obsidian://."""
        urls = {s["label"]: s["url"] for s in self.sources}
        return CITATION_RE.sub(
            lambda m: f"[{m.group(1)}]({urls[m.group(1)]})"
            if m.group(1) in urls
            else m.group(0),
            self.text,
        )


@dataclass
class TeamRun:
    """Результат роботи мультиагентної команди JarLight з експортними артефактами."""

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
    """Фасад сценаріїв робочого місця UC1-UC5 без прив'язки до Streamlit."""

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
        """Повертає URI для прямого відкриття нотатки в застосунку Obsidian."""
        return f"obsidian://open?vault={quote(self.vault_name)}&file={quote(path)}"

    def ask(self, question: str, on_event: OnEvent | None = None) -> Answer:
        """UC1: Запит до бази знань JarLight з верифікацією цитат."""
        result = run_agent(self.kb_agent, question, on_event=on_event)
        found: dict[str, str] = {}
        for output in result.tool_outputs:
            for label, path in SOURCE_RE.findall(output):
                found[label] = path

        cited = CITATION_RE.findall(result.final_text)
        known_notes = {label.split("#")[0] for label in found}
        invalid = sorted(
            {
                c
                for c in cited
                if c not in found and c.split("#")[0] not in known_notes
            }
        )
        sources = [
            {"label": label, "path": path, "url": self.obsidian_url(path)}
            for label, path in found.items()
        ]
        run_id = self.history.add(
            "ask",
            question,
            result.final_text,
            sum(result.llm_calls.values()),
            result.tokens,
            result.seconds,
            details={"sources": list(found), "invalid": invalid},
        )
        return Answer(run_id, result.final_text, sources, invalid, result)

    def run_team(self, request: str, on_event: OnEvent | None = None) -> TeamRun:
        """UC2 & UC3: Запуск МАС JarLight і формування файлів експорту Unity."""
        result = run_agent(self.team_agent, request, on_event=on_event)
        state = result.state
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
        report = str(state.get("report") or result.final_text)

        pr_md = to_draft_pr_md(state, fallback_report=report)
        nunit_tests = to_unity_nunit_tests(state)
        preset_json = to_level_preset_json(state)

        run_id = self.history.add(
            "team",
            request,
            report,
            sum(result.llm_calls.values()),
            result.tokens,
            result.seconds,
            stop_reason,
            details={
                "task_key": task_key,
                "drafts": state.get("drafts", 0),
                "llm_calls": result.llm_calls,
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
            result=result,
        )

    def save_result(self, run: TeamRun, reviewer: str) -> Path:
        """UC4 (Human-in-the-loop): зберігає погоджений результат у Inbox/ сховища."""
        if not self.vault:
            raise RuntimeError("Сховище Obsidian не налаштовано")
        clean_reviewer = reviewer.strip()
        if not clean_reviewer:
            raise ValueError("Потрібно вказати ім'я рецензента")

        note_text = to_vault_note(
            task_key=run.task_key,
            title=run.title,
            report=run.pr_md or run.report,
            run_id=run.run_id,
            reviewer=clean_reviewer,
        )
        note_title = f"{run.task_key} {run.title}"
        path = save_to_vault(self.vault, note_text, note_title, folder="Inbox")
        self.history.mark_saved(run.run_id, str(path))
        return path

    def rate(self, run_id: str, positive: bool) -> None:
        """UC5: зберігає оцінку користувача у SQLite журналі."""
        self.history.rate(run_id, int(positive))


def build_service() -> WorkbenchService:
    """Збирає робочу конфігурацію з .env: Gemini, ChromaDB, Obsidian, SQLite."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from app.agent import build_workflow, gemini
    from app.kb_assistant import build_kb_assistant
    from kb.tools import build_tools

    tools = build_tools()
    team = build_workflow(
        gemini(),
        kb_search=lambda q: tools.search_knowledge(q, skip_inbox=True),
        use_kb_agent=False,
    )
    assistant = build_kb_assistant(gemini(), tools)
    history = HistoryStore(os.getenv("WORKBENCH_DB", "workbench.db"))
    vault_name = os.getenv("OBSIDIAN_VAULT_NAME", tools.vault.name)
    return WorkbenchService(team, assistant, history, tools.vault, vault_name)
