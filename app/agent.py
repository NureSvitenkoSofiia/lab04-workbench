"""Головний граф робочого процесу jarlight-feature-sdlc на Google ADK 2.x."""

from __future__ import annotations

import os
from collections.abc import Callable

from google.adk import Context, Workflow
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.models.base_llm import BaseLlm
from google.adk.workflow import JoinNode
from google.genai import types

from .agents import build_agents
from .kb_connector import build_kb_researcher, search_jarlight_kb
from .nodes import (
    build_clarification_report,
    build_feature_pr,
    intake_task,
    pr_gate,
    readiness_gate,
    reject,
    unity_policy_lint,
)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
KbSearch = Callable[[str], str]


def gemini(model_name: str | None = None) -> Gemini:
    """Повертає налаштовану модель Gemini із повторами при мережевих збоях та 503."""
    return Gemini(
        model=model_name or os.getenv("GEMINI_MODEL", MODEL),
        retry_options=types.HttpRetryOptions(
            attempts=6, initial_delay=2.0, max_delay=25.0, exp_base=2.0
        ),
    )


def build_workflow(
    model: BaseLlm | str,
    kb_search: KbSearch | None = None,
    use_kb_agent: bool = True,
) -> Workflow:
    """Будує граф Workflow з паралельним ревю (JoinNode), лінтом і межею циклу."""
    agents = build_agents(model)
    reviews = JoinNode(name="reviews")
    search_fn = kb_search or search_jarlight_kb

    def retrieve_context(ctx: Context, node_input):
        """Детермінований RAG-крок для швидкого отримання правил JarLight без LLM."""
        req = ctx.state.get("request", "")
        ctx.state["kb_context"] = search_fn(req)
        return node_input

    context_node = (
        build_kb_researcher(model, kb_search=search_fn)
        if use_kb_agent
        else retrieve_context
    )

    return Workflow(
        name="jarlight_feature_sdlc",
        max_concurrency=2,
        edges=[
            ("START", intake_task),
            (intake_task, {"ok": context_node, "reject": reject}),
            (context_node, agents["feature_architect"]),
            (agents["feature_architect"], readiness_gate),
            (
                readiness_gate,
                {
                    "ok": agents["unity_implementer"],
                    "clarify": build_clarification_report,
                },
            ),
            (agents["unity_implementer"], unity_policy_lint),
            (
                unity_policy_lint,
                {
                    "ok": (
                        agents["game_balance_reviewer"],
                        agents["unity_ecs_qa_reviewer"],
                    ),
                    "fix": agents["unity_implementer"],
                    "max_reached": build_feature_pr,
                },
            ),
            (agents["game_balance_reviewer"], reviews),
            (agents["unity_ecs_qa_reviewer"], reviews),
            (reviews, pr_gate),
            (
                pr_gate,
                {
                    "revise": agents["unity_implementer"],
                    "publish": build_feature_pr,
                },
            ),
        ],
    )


root_agent = build_workflow(gemini(), use_kb_agent=True)
app = App(root_agent=root_agent, name="app")
