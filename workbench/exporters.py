"""Експорт артефактів JarLight (Draft PR, Unity NUnit tests, level preset JSON) та Inbox-нотаток."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path


def slugify(title: str) -> str:
    """Безпечне ім'я файла (кирилиця, латиниця, цифри, дефіси, пробіли)."""
    cleaned = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", cleaned)[:80] or "jarlight-feature"


def to_draft_pr_md(state: dict, fallback_report: str = "") -> str:
    """Формує Markdown-файл Draft Feature PR зі стану МАС."""
    report = (state.get("report") or fallback_report or "").strip()
    return (report[:12000] + "\n") if report else "# Draft Feature PR (порожній звіт)\n"


def to_unity_nunit_tests(state: dict) -> str:
    """Виділяє C# файл NUnit-тестів для Unity Test Framework."""
    impl = state.get("implementation") or {}
    code = (impl.get("unity_nunit_tests") or "").strip()
    if not code:
        return ""
    if "using NUnit.Framework;" not in code:
        code = "using NUnit.Framework;\n\n" + code
    return code + "\n"


def to_level_preset_json(state: dict) -> str:
    """Форматує JSON пресет демонстраційного рівня або ScriptableObject."""
    impl = state.get("implementation") or {}
    raw = (impl.get("level_preset_json") or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
    except Exception:
        return raw + "\n"


def to_vault_note(
    task_key: str,
    title: str,
    report: str,
    run_id: str,
    reviewer: str,
) -> str:
    """Створює Markdown-нотатку з YAML frontmatter для папки Inbox/ сховища Obsidian."""
    tags = "[jarlight, feature-pr, generated, approved]"
    return (
        f"---\n"
        f"id: {slugify(task_key).lower()}\n"
        f"title: \"{task_key}: {title}\"\n"
        f"status: draft\n"
        f"tags: {tags}\n"
        f"source: \"workbench run {run_id}\"\n"
        f"approved_by: \"{reviewer}\"\n"
        f"updated: {date.today().isoformat()}\n"
        f"---\n\n"
        f"{report.strip()}\n"
    )


def save_to_vault(
    vault: Path, note_text: str, title: str, folder: str = "Inbox"
) -> Path:
    """Пише нотатку лише в папку Inbox/ без перезапису і з блокуванням path traversal."""
    root = vault.resolve()
    target_dir = (root / folder).resolve()
    if not target_dir.is_relative_to(root):
        raise ValueError("Спроба запису за межами сховища Obsidian")
    target_dir.mkdir(parents=True, exist_ok=True)
    base = slugify(title)
    path = target_dir / f"{base}.md"
    idx = 2
    while path.exists():
        path = target_dir / f"{base} ({idx}).md"
        idx += 1
    path.write_text(note_text, encoding="utf-8")
    return path
