"""Детерміновані вузли контролю, валідації Unity ECS і маршрутизації для jarlight-feature-sdlc."""

from __future__ import annotations

import json
import re
from typing import Any

from google.adk import Context, Event
from google.genai import types

MAX_ROUNDS = 3
MAX_CODE_LEN = 3800

TASK_KEY_RE = re.compile(r"\b(JL-\d+)\b", re.IGNORECASE)
ALNUM_RE = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9]")
SECRET_RE = re.compile(r"""(AIza[0-9A-Za-z_-]{20,}|password\s*=\s*['"][^'"]+['"])""")


def extract_task_key(text: str) -> str:
    """Виділяє ідентифікатор задачі JarLight (JL-XX) або повертає JL-NEW."""
    m = TASK_KEY_RE.search(text or "")
    return m.group(1).upper() if m else "JL-NEW"


def _make_text_event(text: str, route: str | None = None) -> Event:
    kwargs: dict[str, Any] = {
        "output": text,
        "content": types.Content(role="model", parts=[types.Part(text=text)]),
    }
    if route is not None:
        kwargs["route"] = route
    return Event(**kwargs)


def intake_task(ctx: Context, node_input: str) -> Event:
    """Вузол прийому: перевіряє змістовність GDD-запиту без виклику LLM."""
    raw = (node_input or "").strip()
    alnum_count = len(ALNUM_RE.findall(raw))
    if len(raw) < 15 or alnum_count < 8:
        ctx.state["stop_reason"] = "rejected_invalid_input"
        ctx.state["report"] = (
            "# Запит відхилено\n\n"
            "Опис задачі для JarLight надто короткий або не містить змістовних вимог "
            f"(отримано {len(raw)} симв., {alnum_count} алфавітно-цифрових знаків)."
        )
        return _make_text_event("Невалідний або занадто короткий опис задачі.", route="reject")

    key = extract_task_key(raw)
    ctx.state["request"] = raw
    ctx.state["task_key"] = key
    ctx.state["drafts"] = 0
    ctx.state["lint_passed"] = False
    ctx.state["lint_errors"] = ""
    ctx.state["review_feedback"] = ""
    ctx.state["stop_reason"] = ""
    return _make_text_event(f"Прийнято задачу {key}", route="ok")


def reject(ctx: Context) -> Event:
    """Термінальний вузол відхилення некоректного входу."""
    report = ctx.state.get("report") or "# Запит відхилено\n\nНекоректний формат задачі."
    ctx.state["report"] = report
    return _make_text_event(report)


def readiness_gate(ctx: Context) -> Event:
    """Гейт готовності вимог: блокує генерацію C# коду для нечітких GDD-задач."""
    plan: dict[str, Any] = ctx.state.get("plan") or {}
    status = plan.get("readiness_status", "needs_clarification")
    score = int(plan.get("readiness_score") or 0)
    if status != "ready" or score < 3:
        ctx.state["stop_reason"] = "needs_clarification"
        return _make_text_event("Потрібне уточнення вимог GDD", route="clarify")
    return _make_text_event("Вимоги готові до реалізації", route="ok")


def build_clarification_report(ctx: Context) -> Event:
    """Формує звіт із уточнювальними запитаннями для геймдизайнера JarLight."""
    plan: dict[str, Any] = ctx.state.get("plan") or {}
    key = plan.get("task_key") or ctx.state.get("task_key", "JL-NEW")
    title = plan.get("title") or "Невизначена механіка JarLight"
    questions = plan.get("clarification_questions") or [
        "Уточніть оптичні елементи, вплив на Par Moves та умови перемоги."
    ]
    ctx.state["stop_reason"] = "needs_clarification"
    q_lines = "\n".join(f"- {q}" for q in questions)
    report = (
        f"# [{key}] Потрібне уточнення вимог: {title}\n\n"
        f"**Readiness score:** {plan.get('readiness_score', 1)}/5 (`needs_clarification`)\n\n"
        f"## Запитання до геймдизайнера\n{q_lines}\n"
    )
    ctx.state["report"] = report
    return _make_text_event(report)


def validate_unity_bundle(impl: dict[str, Any]) -> list[str]:
    """Детермінована перевірка коду C# Unity ECS, пресету JSON і NUnit-тестів."""
    errors: list[str] = []
    if not impl:
        return ["Відсутній об'єкт implementation у стані сесії."]

    if not impl.get("ecs_changes"):
        errors.append("ecs_changes має містити хоча б один опис ECS/ScriptableObject зміни.")

    snippet = (impl.get("csharp_snippets") or "").strip()
    if len(snippet) < 30:
        errors.append("csharp_snippets надто короткий або порожній (мінімум 30 символів).")
    elif len(snippet) > MAX_CODE_LEN:
        errors.append(f"csharp_snippets перевищує межу {MAX_CODE_LEN} символів.")

    nunit = (impl.get("unity_nunit_tests") or "").strip()
    if ("[Test]" not in nunit and "[UnityTest]" not in nunit) or "Assert." not in nunit:
        errors.append("unity_nunit_tests має містити атрибути [Test]/[UnityTest] і Assert.")

    raw_json = (impl.get("level_preset_json") or "").strip()
    try:
        parsed = json.loads(raw_json)
        if not isinstance(parsed, dict) or not parsed:
            errors.append("level_preset_json має бути непорожнім JSON-об'єктом.")
    except Exception as exc:
        errors.append(f"level_preset_json містить невалідний JSON: {exc}")

    combined = f"{snippet}\n{nunit}"
    if "GameObject.Find(" in combined or "Resources.Load(" in combined:
        errors.append("Заборонено використовувати GameObject.Find() або Resources.Load() у Burst/ECS коді.")
    if "eval(" in combined or "unsafe {" in combined:
        errors.append("Виявлено небезпечні конструкції (unsafe/eval) у C# фрагменті.")
    if SECRET_RE.search(combined):
        errors.append("Виявлено потенційно захардкоджений секрет або API-ключ у коді.")

    return errors


def unity_policy_lint(ctx: Context) -> Event:
    """Перевіряє артефакти Unity інженера, обліковує drafts і контролює ліміт."""
    drafts = int(ctx.state.get("drafts") or 0) + 1
    ctx.state["drafts"] = drafts
    impl: dict[str, Any] = ctx.state.get("implementation") or {}
    errors = validate_unity_bundle(impl)

    if errors:
        ctx.state["lint_passed"] = False
        ctx.state["lint_errors"] = "\n".join(f"- {e}" for e in errors)
        if drafts >= MAX_ROUNDS:
            ctx.state["stop_reason"] = "max_drafts"
            return _make_text_event(
                f"Лінт не пройдено на чернетці {drafts}/{MAX_ROUNDS}; досягнуто ліміту.",
                route="max_reached",
            )
        return _make_text_event(
            f"Лінт виявив {len(errors)} порушень (чернетка {drafts}/{MAX_ROUNDS}).",
            route="fix",
        )

    ctx.state["lint_passed"] = True
    ctx.state["lint_errors"] = ""
    return _make_text_event(f"Лінт та політика Burst/ECS пройдені (чернетка {drafts}).", route="ok")


def pr_gate(ctx: Context) -> Event:
    """Об'єднує паралельні рев'ю балансу і Unity QA та обмежує цикл доопрацювань."""
    drafts = int(ctx.state.get("drafts") or 1)
    bal: dict[str, Any] = ctx.state.get("balance_review") or {}
    qa: dict[str, Any] = ctx.state.get("qa_review") or {}

    bal_ok = bal.get("verdict") == "approve"
    qa_ok = qa.get("verdict") == "approve"

    if bal_ok and qa_ok:
        ctx.state["stop_reason"] = "approved"
        return _make_text_event("Обидва рев'ю затвердили зміни.", route="publish")

    fixes: list[str] = []
    if not bal_ok:
        fixes.extend(bal.get("issues") or [])
        fixes.extend(bal.get("required_fixes") or [])
    if not qa_ok:
        fixes.extend(qa.get("missing_scenarios") or [])
        fixes.extend(qa.get("required_fixes") or [])

    ctx.state["review_feedback"] = "\n".join(f"- {f}" for f in fixes) or "- Доопрацювати зауваження рев'ю."

    if drafts >= MAX_ROUNDS:
        ctx.state["stop_reason"] = "max_drafts"
        return _make_text_event(
            f"Досягнуто ліміт {MAX_ROUNDS} чернеток; публікація чернетки.",
            route="publish",
        )
    return _make_text_event(
        f"Потрібне доопрацювання (чернетка {drafts}/{MAX_ROUNDS}).",
        route="revise",
    )


def build_feature_pr(ctx: Context) -> Event:
    """Детерміновано збирає фінальний пакет Draft PR для фічі JarLight зі стану сесії."""
    plan: dict[str, Any] = ctx.state.get("plan") or {}
    impl: dict[str, Any] = ctx.state.get("implementation") or {}
    bal: dict[str, Any] = ctx.state.get("balance_review") or {}
    qa: dict[str, Any] = ctx.state.get("qa_review") or {}
    drafts = int(ctx.state.get("drafts") or 0)
    stop_reason = ctx.state.get("stop_reason") or "approved"

    key = impl.get("task_key") or plan.get("task_key") or ctx.state.get("task_key", "JL-NEW")
    title = plan.get("title") or f"Реалізація {key} у JarLight"
    branch = impl.get("branch_name") or f"feat/{key.lower()}-mechanic"

    ecs_md = "\n".join(f"- {x}" for x in (impl.get("ecs_changes") or [])) or "- Не вказано"
    lvl_md = "\n".join(f"- {x}" for x in (impl.get("level_design_changes") or [])) or "- Не вказано"
    ac_md = "\n".join(f"- {x}" for x in (plan.get("acceptance_criteria") or [])) or "- Не вказано"
    assump_md = "\n".join(f"- {x}" for x in (impl.get("assumptions") or [])) or "- Немає додаткових припущень"

    report = (
        f"# draft: [{key}] {title}\n\n"
        f"**Task:** `{key}` | **Branch:** `{branch}` | "
        f"**Status:** `{stop_reason}` (чернеток: {drafts}/{MAX_ROUNDS})\n\n"
        f"## 1. Оцінка вимог та підсистеми JarLight\n"
        f"- **Readiness:** `{plan.get('readiness_status', 'ready')}` ({plan.get('readiness_score', 4)}/5)\n"
        f"- **Системи Unity:** {', '.join(plan.get('affected_systems') or ['ECS', 'Optics'])}\n\n"
        f"### Критерії приймання\n{ac_md}\n\n"
        f"## 2. Зміни Unity ECS та левел-дизайну\n"
        f"{impl.get('summary', '')}\n\n"
        f"### C# ECS / EventBus\n{ecs_md}\n\n"
        f"### ScriptableObjects / Рівні\n{lvl_md}\n\n"
        f"### Фрагмент C# коду\n```csharp\n{impl.get('csharp_snippets', '')}\n```\n\n"
        f"### Пресет конфігурації рівня (JSON)\n```json\n{impl.get('level_preset_json', '{}')}\n```\n\n"
        f"## 3. Тести Unity Test Framework (NUnit)\n```csharp\n{impl.get('unity_nunit_tests', '')}\n```\n\n"
        f"## 4. Результати верифікації\n"
        f"- **Статичний лінт Burst/ECS:** {'OK' if ctx.state.get('lint_passed') else 'ERROR'}\n"
        f"- **Game Balance Review:** `{bal.get('verdict', 'n/a')}` "
        f"(оптика {bal.get('optics_integrity_score', '—')}/5, баланс {bal.get('balance_score', '—')}/5)\n"
        f"- **Unity ECS QA Review:** `{qa.get('verdict', 'n/a')}` "
        f"(Burst {qa.get('burst_safety_score', '—')}/5, тести {qa.get('test_coverage_score', '—')}/5)\n\n"
        f"## 5. Припущення та використаний контекст БЗ\n{assump_md}\n"
    )

    ctx.state["pr_draft"] = {
        "task_key": key,
        "pr_title": f"[{key}] {title}",
        "branch": branch,
        "stop_reason": stop_reason,
        "drafts": drafts,
    }
    ctx.state["report"] = report
    return _make_text_event(report)
