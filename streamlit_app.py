"""Вебінтерфейс робочого місця Unity-розробника JarLight (ЛР 2 + ЛР 3 у Streamlit).

Запуск: uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from workbench.exporters import to_bundle_zip
from workbench.service import TeamRun, WorkbenchService, build_service

MAX_TEAM_RUNS = 10

STAGE_PROGRESS = {
    "intake_task": 0.10,
    "retrieve_context": 0.20,
    "feature_architect": 0.35,
    "readiness_gate": 0.45,
    "unity_implementer": 0.65,
    "unity_policy_lint": 0.75,
    "game_balance_reviewer": 0.85,
    "unity_ecs_qa_reviewer": 0.85,
    "reviews": 0.90,
    "pr_gate": 0.95,
    "build_feature_pr": 1.00,
    "build_clarification_report": 1.00,
    "reject": 1.00,
}

STAGE_TITLES = {
    "intake_task": "Валідація GDD-задачі",
    "retrieve_context": "Пошук правил оптики та ECS у БЗ",
    "feature_architect": "Оцінка вимог і формування плану",
    "readiness_gate": "Перевірка готовності вимог",
    "unity_implementer": "Генерація C# ECS коду, JSON-пресету та NUnit тестів",
    "unity_policy_lint": "Статичний лінт Burst/ECS і перевірка політики безпеки",
    "game_balance_reviewer": "Рев'ю оптики RGB та балансу Par Moves",
    "unity_ecs_qa_reviewer": "Перевірка Burst-безпеки та NUnit покриття",
    "reviews": "Синхронізація паралельних рецензій (JoinNode)",
    "pr_gate": "Консолідація вердиктів і контроль циклу",
    "build_feature_pr": "Формування пакета Draft Feature PR",
    "build_clarification_report": "Підготовка списку запитань геймдизайнеру",
    "reject": "Відхилення некоректного запиту",
}


@st.cache_resource
def _cached_service() -> WorkbenchService:
    return build_service()


def _resolve_service() -> WorkbenchService | None:
    if "service" in st.session_state:
        return st.session_state["service"]
    try:
        return _cached_service()
    except Exception as exc:
        st.error(f"Не вдалося запустити сервіс: {exc}")
        st.info(
            "Перевірте файл .env (GEMINI_API_KEY, KB_VAULT_PATH, CHROMA_PERSIST_DIR) "
            "та індекс бази знань ЛР 2."
        )
        return None


def _render_kb_tab(svc: WorkbenchService) -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input(
        "Запитайте про оптику RGB, призми, Par Moves, кристали або Unity ECS JarLight"
    )
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.status("Агент шукає в базі знань JarLight…", expanded=False) as status:
        def _log_kb(event: dict) -> None:
            if event["author"] != "user" and event["text"]:
                status.write(f"{event['author']}: {event['text'][:90]}")

        answer = svc.ask(question, on_event=_log_kb)
        status.update(label="Відповідь готова", state="complete")

    links_block = "\n".join(f"- [{src['label']}]({src['url']})" for src in answer.sources)
    rendered = answer.linked_text
    if links_block:
        rendered += f"\n\n**Фрагменти, знайдені агентом:**\n{links_block}"
    if answer.invalid_citations:
        rendered += "\n\n:warning: Посилання без підтвердження: " + ", ".join(
            answer.invalid_citations
        )
    st.session_state.messages.append({"role": "assistant", "content": rendered})
    st.rerun()


def _render_exports_and_hitl(svc: WorkbenchService, run: TeamRun) -> None:
    metrics = st.columns(4)
    metrics[0].metric("Чернеток", run.result.state.get("drafts", "—"))
    metrics[1].metric("Викликів LLM", sum(run.result.llm_calls.values()))
    metrics[2].metric("Токенів", run.result.tokens)
    metrics[3].metric("Час, с", run.result.seconds)

    st.markdown(run.report)

    if run.nunit_tests or run.preset_json:
        with st.expander("Попередній перегляд експорту Unity (NUnit C# і JSON-пресет)"):
            if run.nunit_tests:
                st.code(run.nunit_tests, language="csharp")
            if run.preset_json:
                st.code(run.preset_json, language="json")

    slug = run.task_key.lower()
    col_pr, col_cs, col_json, col_zip = st.columns(4)
    col_pr.download_button(
        "Завантажити draft_pr.md",
        run.pr_md,
        file_name=f"{slug}_draft_pr.md",
    )
    if run.nunit_tests:
        col_cs.download_button(
            "Завантажити FeatureTests.cs",
            run.nunit_tests,
            file_name=f"{slug}_FeatureTests.cs",
        )
    if run.preset_json:
        col_json.download_button(
            "Завантажити level_preset.json",
            run.preset_json,
            file_name=f"{slug}_preset.json",
        )
    col_zip.download_button(
        "Завантажити все (ZIP)",
        to_bundle_zip(slug, run.pr_md, run.nunit_tests, run.preset_json),
        file_name=f"{slug}_bundle.zip",
        mime="application/zip",
    )

    st.subheader("Перевірка людиною (Human-in-the-loop)")
    reviewer = st.text_input("Ваше ім'я (рецензент)")
    confirmed = st.checkbox(
        "Я перевірив план, C# ECS код, JSON-пресет, NUnit тести та результати рев'ю"
    )
    if st.button(
        "Зберегти в Obsidian (Inbox)",
        disabled=not (confirmed and reviewer.strip()),
    ):
        saved_path = svc.save_result(run, reviewer)
        st.success(
            f"Збережено в Inbox: {saved_path.name}. Переіндексуйте базу знань за потреби."
        )

    rating = st.feedback("thumbs", key=f"rate_{run.run_id}")
    if rating is not None:
        svc.rate(run.run_id, positive=bool(rating))


def _render_team_tab(svc: WorkbenchService) -> None:
    session = st.session_state
    with st.form("team_form"):
        task_text = st.text_area(
            "Опис GDD-задачі для етапу Конструювання",
            height=120,
            placeholder=(
                "JL-24: Реалізувати елемент PrismSplitter у Unity ECS/Burst: розщеплення білого "
                "променя на R, G, B під кутом 60 град., ліміт max_bounces=8, JSON-пресет рівня "
                "(Par Moves <= 7) та NUnit тести."
            ),
        )
        submitted = st.form_submit_button(
            "Запустити команду",
            disabled=session.team_runs >= MAX_TEAM_RUNS,
        )

    if submitted and task_text.strip():
        session.team_runs += 1
        with st.status("Команда агентів працює (орієнтовно 20–50 с)…", expanded=True) as status:
            progress = st.progress(0.0, text="Ініціалізація конвеєра…")

            def _on_step(event: dict) -> None:
                node_name = event["node"].split("@")[0]
                if node_name not in STAGE_TITLES:
                    return
                route_suffix = f" → {event['route']}" if event["route"] else ""
                elapsed_prefix = f"[{event['t']:.1f} с] " if "t" in event else ""
                step_title = STAGE_TITLES[node_name]
                progress.progress(
                    STAGE_PROGRESS.get(node_name, 0.5),
                    text=f"{elapsed_prefix}{step_title}",
                )
                status.write(f"{elapsed_prefix}{step_title}{route_suffix}")

            session.last_run = svc.run_team(task_text.strip(), on_event=_on_step)
            progress.progress(1.0, text="Завершено")
            status.update(label="Готово", state="complete", expanded=False)

    last_run = session.get("last_run")
    if last_run is not None:
        _render_exports_and_hitl(svc, last_run)


def _render_history_tab(svc: WorkbenchService) -> None:
    stats = svc.history.summary()
    cards = st.columns(4)
    cards[0].metric("Запусків", stats["runs"] or 0)
    cards[1].metric("Сер. викликів LLM", round(stats["avg_calls"] or 0, 1))
    cards[2].metric("Сер. час, с", round(stats["avg_seconds"] or 0, 1))
    share = stats["positive_share"]
    cards[3].metric("Позитивних оцінок", "—" if share is None else f"{share:.0%}")

    filter_choice = st.selectbox(
        "Фільтр за типом запуску",
        options=["Усі", "ask", "team"],
        index=0,
    )
    kind_filter = None if filter_choice == "Усі" else filter_choice
    rows = svc.history.list(kind=kind_filter)
    if not rows:
        st.caption("Запусків ще немає.")
        return

    frame = pd.DataFrame(rows)
    st.dataframe(frame, hide_index=True)
    st.caption(
        "Примітка: колонка saved_path заповнюється після підтвердження збереження в Obsidian (Inbox)."
    )
    st.download_button(
        "Експорт CSV",
        frame.to_csv(index=False),
        file_name="runs.csv",
        mime="text/csv",
    )


def _render_sidebar(svc: WorkbenchService) -> None:
    with st.sidebar:
        st.header("Робоче місце розробника")
        st.caption("Етап ЖЦ ПЗ: 4 — Конструювання (JarLight Unity)")
        st.metric("Запусків команди в сесії", f"{st.session_state.team_runs} / {MAX_TEAM_RUNS}")
        st.caption(f"Сховище Obsidian: {svc.vault_name or 'не налаштовано'}")
        st.divider()
        st.caption("Ключові інваріанти JarLight:")
        st.markdown("- `max_bounces = 8` (призми)\n- Спектр RGB: `60°`\n- Гекса-сітка + `BurstCompile`")


def main() -> None:
    st.set_page_config(
        page_title="Робоче місце розробника JarLight",
        page_icon="💡",
        layout="wide",
    )
    svc = _resolve_service()
    if svc is None:
        st.stop()

    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("team_runs", 0)

    tab_ask, tab_team, tab_history = st.tabs(
        ["Питання до бази знань", "Команда агентів", "Історія і метрики"]
    )
    with tab_ask:
        _render_kb_tab(svc)
    with tab_team:
        _render_team_tab(svc)
    with tab_history:
        _render_history_tab(svc)

    _render_sidebar(svc)


main()
