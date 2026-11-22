"""Демонстраційний режим робочого місця JarLight без API ключа Gemini (крок 11).

Запуск: PYTHONPATH=. uv run streamlit run tests/demo_app.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import streamlit as st

from app.agent import build_workflow
from app.kb_assistant import build_kb_assistant
from kb.store import KnowledgeStore
from kb.tools import HashEmbedder, KnowledgeTools, index_vault
from tests.fixtures import BAL, GOOD, PLAN, QA
from tests.scripted import ScriptedLlm, ToolCallingLlm
from workbench.service import WorkbenchService
from workbench.storage import HistoryStore

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def demo_service() -> WorkbenchService:
    tmp = Path(tempfile.mkdtemp(prefix="jarlight_demo_"))
    vault = tmp / "kb-vault"
    shutil.copytree(ROOT / "tests" / "vault", vault)

    embedder = HashEmbedder()
    store = KnowledgeStore(collection_name="demo_jarlight", persist_dir=tmp / "chroma")
    index_vault(vault, store, embedder)
    tools = KnowledgeTools(store=store, vault=vault, embedder=embedder, top_k=3, max_distance=1.5)

    team = ScriptedLlm(
        model="demo",
        script={
            "jarlight_feature_architect": [PLAN],
            "jarlight_unity_implementer": [GOOD],
            "jarlight_balance_reviewer": [BAL],
            "jarlight_ecs_qa_reviewer": [QA],
        },
    )

    class DemoKb(ToolCallingLlm):
        async def generate_content_async(self, llm_request, stream=False):
            last = (
                llm_request.contents[-1].parts[0]
                if llm_request.contents and llm_request.contents[-1].parts
                else None
            )
            if not self.calls and not (last and last.function_response):
                self.calls = [("search_knowledge", {"query": "призма дисперсії RGB"})]
            async for r in super().generate_content_async(llm_request, stream):
                yield r

    kb_model = DemoKb(
        model="demo",
        answer=(
            "Білий промінь розщеплюється на три складові R, G, B під кутом 60 градусів "
            "з обмеженням max_bounces = 8 [[Призми дисперсії та розщеплення світлових пучків#Принцип розщеплення променів]]."
        ),
    )
    return WorkbenchService(
        team_agent=build_workflow(team, kb_search=tools.search_knowledge, use_kb_agent=False),
        kb_agent=build_kb_assistant(kb_model, tools),
        history=HistoryStore(tmp / "history.db"),
        vault=vault,
        vault_name="kb-vault",
    )


st.session_state.setdefault("service", demo_service())
exec((ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
