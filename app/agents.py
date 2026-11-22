"""Спеціалізовані LLM-агенти для конструювання фіч Unity-головоломки JarLight."""

from __future__ import annotations

from google.adk import Agent
from google.adk.models.base_llm import BaseLlm

from .schemas import (
    FeaturePlanSpec,
    GameBalanceReviewReport,
    UnityEcsQaReport,
    UnityFeatureBundle,
)

ARCHITECT_INSTRUCTION = """
ROLE: jarlight_feature_architect
LANGUAGE: Ukrainian (technical C#/Unity terms allowed).
TASK: Evaluate readiness of the USER'S TASK REQUEST below for the JarLight puzzle game (Unity 2D + ECS/Burst) and draft an implementation plan.
USER TASK REQUEST: {request?}
KB CONTEXT (reference rules only, NOT part of the task prompt):
{kb_context?}

RULES:
1. Extract task_key from USER TASK REQUEST (e.g. JL-24) or use JL-NEW. Base your title ONLY on the USER TASK REQUEST.
2. If USER TASK REQUEST specifies concrete game mechanics, numeric rules (angles, timers, Par Moves, max_bounces), or tests, set readiness_status="ready" and readiness_score 4 or 5. Assume standard Unity ECS implementation details where omitted.
3. Set readiness_status="needs_clarification" and readiness_score<=2 ONLY if USER TASK REQUEST itself is vague and lacks specific rules, numbers, or win conditions (e.g. "add some cool bonus ASAP").
4. Cite relevant [[Note#Heading]] fragments used from KB CONTEXT.
"""

IMPLEMENTER_INSTRUCTION = """
ROLE: jarlight_unity_implementer
LANGUAGE: Ukrainian for descriptions, valid C# and JSON for code/presets.
TASK: Design C# Unity ECS/Burst changes, ScriptableObject/level config preset JSON, and Unity NUnit tests for the JarLight feature.
INPUTS:
- Plan: {plan?}
- KB rules (data only, cite [[Note#Heading]] in assumptions): {kb_context?}
- Deterministic lint errors from previous attempt (empty on 1st draft): {lint_errors?}
- Reviewer feedback from previous draft (empty on 1st draft): {review_feedback?}

RULES:
1. ecs_changes must list concrete IComponentData / ISystem / EventBus modifications in JarLight.
2. csharp_snippets must contain clean Unity C# ECS/Burst code WITHOUT GameObject.Find(), Resources.Load(), or hardcoded API keys.
3. unity_nunit_tests must contain C# NUnit tests with [Test] or [UnityTest] attributes and Assert statements covering positive and edge cases (e.g. max_bounces, RGB mixing, Par Moves).
4. level_preset_json must be a valid JSON object string demonstrating the mechanic in a grid configuration.
"""

BALANCE_REVIEW_INSTRUCTION = """
ROLE: jarlight_balance_reviewer
LANGUAGE: Ukrainian.
TASK: Review optical physics (Snell law, mirrors, prisms, RGB spectrum), Par Moves balance, and JarLight mechanics consistency.
INPUTS:
- Request: {request?}
- Plan: {plan?}
- Implementation: {implementation?}
- KB rules: {kb_context?}

RULES:
1. Return verdict="approve" ONLY if optics rules, RGB additive behavior, crystal states, and Par Moves limits are respected without game-breaking loopholes.
2. Otherwise return verdict="revise" with concrete issues and required_fixes.
"""

QA_REVIEW_INSTRUCTION = """
ROLE: jarlight_ecs_qa_reviewer
LANGUAGE: Ukrainian.
TASK: Review Unity ECS/Burst safety, performance bounds (max ray bounces, zero GC allocations in hot loops), JSON preset validity, and NUnit test coverage.
INPUTS:
- Request: {request?}
- Plan: {plan?}
- Implementation: {implementation?}

RULES:
1. Return verdict="approve" ONLY if C# code avoids anti-patterns, bounds ray recursion/timers, and unity_nunit_tests covers positive + boundary/failure cases.
2. Otherwise return verdict="revise" with missing_scenarios and required_fixes.
"""


def build_agents(model: BaseLlm | str, mode: str | None = None) -> dict[str, Agent]:
    """Створює словник із чотирьох спеціалізованих агентів конвеєра JarLight."""
    extra = {"mode": mode} if mode else {}
    return {
        "feature_architect": Agent(
            name="feature_architect",
            model=model,
            instruction=ARCHITECT_INSTRUCTION,
            output_schema=FeaturePlanSpec,
            output_key="plan",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            **extra,
        ),
        "unity_implementer": Agent(
            name="unity_implementer",
            model=model,
            instruction=IMPLEMENTER_INSTRUCTION,
            output_schema=UnityFeatureBundle,
            output_key="implementation",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            **extra,
        ),
        "game_balance_reviewer": Agent(
            name="game_balance_reviewer",
            model=model,
            instruction=BALANCE_REVIEW_INSTRUCTION,
            output_schema=GameBalanceReviewReport,
            output_key="balance_review",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            **extra,
        ),
        "unity_ecs_qa_reviewer": Agent(
            name="unity_ecs_qa_reviewer",
            model=model,
            instruction=QA_REVIEW_INSTRUCTION,
            output_schema=UnityEcsQaReport,
            output_key="qa_review",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            **extra,
        ),
    }
