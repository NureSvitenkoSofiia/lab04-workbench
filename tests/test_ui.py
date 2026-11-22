"""Тести Streamlit-інтерфейсу без браузера (AppTest) із підмінним сервісом."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def start(service) -> AppTest:
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60)
    at.session_state["service"] = service
    return at.run()


def test_three_tabs_render_without_errors(service) -> None:
    at = start(service)
    assert not at.exception
    assert [t.label for t in at.tabs] == [
        "Питання до бази знань",
        "Команда агентів",
        "Історія і метрики",
    ]


def test_chat_displays_verified_obsidian_links(service) -> None:
    at = start(service)
    at.chat_input[0].set_value("Як працює дисперсія світла?").run()
    assistant = [m for m in at.chat_message if m.name == "assistant"]
    text = assistant[-1].markdown[0].value
    assert "obsidian://open?vault=kb-vault" in text
    assert "Фрагменти, знайдені агентом:" in text


def test_team_run_export_and_human_in_the_loop(service) -> None:
    at = start(service)
    at.text_area[0].input(
        "JL-24: Реалізувати PrismSplitter у Unity ECS з розщепленням R/G/B."
    )
    at.button[0].click().run()
    assert any("Призма дисперсії PrismSplitter" in md.value for md in at.markdown)
    save_btn = next(b for b in at.button if b.label == "Зберегти в Obsidian (Inbox)")
    assert save_btn.disabled

    at.text_input[0].input("Світенко")
    at.checkbox[0].check().run()
    next(b for b in at.button if b.label == "Зберегти в Obsidian (Inbox)").click().run()
    assert any("Збережено в Inbox" in s.value for s in at.success)
    assert list((service.vault / "Inbox").glob("*.md"))


def test_missing_configuration_is_reported(monkeypatch) -> None:
    monkeypatch.setenv("KB_VAULT_PATH", "")
    monkeypatch.setenv("OBSIDIAN_VAULT", "")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", "")
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60).run()
    assert not at.exception
    assert "Не вдалося запустити сервіс" in at.error[0].value
