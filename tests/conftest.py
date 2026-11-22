"""Спільні фікстури pytest: тимчасове сховище JarLight, ChromaDB і сервіс без API."""

from __future__ import annotations

import shutil
from pathlib import Path

import chromadb
import pytest

from app.agent import build_workflow
from app.kb_assistant import build_kb_assistant
from kb.store import KnowledgeStore
from kb.tools import HashEmbedder, KnowledgeTools, index_vault
from tests.fixtures import BAL, GOOD, PLAN, QA
from tests.scripted import ScriptedLlm, ToolCallingLlm
from workbench.service import WorkbenchService
from workbench.storage import HistoryStore


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    target = tmp_path / "kb-vault"
    shutil.copytree(Path(__file__).parent / "vault", target)
    return target


@pytest.fixture
def kb_tools(vault: Path, tmp_path: Path) -> KnowledgeTools:
    embedder = HashEmbedder()
    store = KnowledgeStore(collection_name="test_jarlight", persist_dir=tmp_path / "chroma")
    index_vault(vault, store, embedder)
    return KnowledgeTools(store=store, vault=vault, embedder=embedder, top_k=3, max_distance=1.5)


@pytest.fixture
def service(kb_tools: KnowledgeTools, vault: Path, tmp_path: Path) -> WorkbenchService:
    team_model = ScriptedLlm(
        model="scripted",
        script={
            "jarlight_feature_architect": [PLAN],
            "jarlight_unity_implementer": [GOOD],
            "jarlight_balance_reviewer": [BAL],
            "jarlight_ecs_qa_reviewer": [QA],
        },
    )
    kb_model = ToolCallingLlm(
        model="scripted",
        calls=[("search_knowledge", {"query": "розщеплення променів призми"})],
        answer="Білий промінь розщеплюється на R, G, B під кутом 60 градусів [[Призми дисперсії та розщеплення світлових пучків#Принцип розщеплення променів]].",
    )
    return WorkbenchService(
        team_agent=build_workflow(
            team_model, kb_search=kb_tools.search_knowledge, use_kb_agent=False
        ),
        kb_agent=build_kb_assistant(kb_model, kb_tools),
        history=HistoryStore(tmp_path / "history.db"),
        vault=vault,
        vault_name="kb-vault",
    )
