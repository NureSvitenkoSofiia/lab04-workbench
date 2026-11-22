"""Наскрізний тест Playwright (просунутий крок 14) для демонстраційного режиму JarLight."""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def demo_url():
    external = os.getenv("DEMO_URL")
    if external:
        yield external
        return

    port = 8521
    env = {**os.environ, "PYTHONPATH": ROOT}
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "streamlit",
            "run",
            "tests/demo_app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    url = f"http://localhost:{port}"
    try:
        for _ in range(40):
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Streamlit demo server failed to start in time")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_playwright_demo_end_to_end(demo_url: str) -> None:
    with sync_playwright() as p:
        try:
            if os.name == "nt":
                browser = p.chromium.launch(channel="chrome", headless=True)
            else:
                browser = p.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Playwright browser unavailable in this environment: {exc}")

        page = browser.new_page()
        try:
            page.goto(demo_url, wait_until="domcontentloaded")

            chat_box = page.get_by_placeholder(
                "Запитайте про оптику RGB, призми, Par Moves, кристали або Unity ECS JarLight"
            )
            chat_box.fill("Як працює призма дисперсії RGB?")
            chat_box.press("Enter")
            page.get_by_text("Фрагменти, знайдені агентом:").wait_for(timeout=15000)

            page.get_by_role("tab", name="Команда агентів").click()
            textarea = page.get_by_label("Опис GDD-задачі для етапу Конструювання")
            textarea.fill("JL-24: Додати PrismSplitter у Unity ECS з розщепленням R/G/B.")
            page.get_by_role("button", name="Запустити команду").click()
            page.get_by_text("Перевірка людиною (Human-in-the-loop)").wait_for(timeout=20000)
            assert page.get_by_role("button", name="Завантажити draft_pr.md").is_visible()
            assert page.get_by_role("button", name="Зберегти в Obsidian (Inbox)").is_disabled()

            page.get_by_role("tab", name="Історія і метрики").click()
            page.get_by_role("button", name="Експорт CSV").wait_for(timeout=10000)
        finally:
            browser.close()
