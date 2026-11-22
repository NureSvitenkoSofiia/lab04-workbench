"""Фікстури відповідей агентів для офлайн-тестів робочого місця JarLight."""

from __future__ import annotations

import json

PLAN = json.dumps(
    {
        "task_key": "JL-24",
        "title": "Призма дисперсії PrismSplitter у Unity ECS",
        "readiness_status": "ready",
        "readiness_score": 5,
        "clarification_questions": [],
        "affected_systems": ["Optics", "ECS", "LevelDesign"],
        "acceptance_criteria": [
            "Given білий промінь, When влучає у PrismSplitter, Then генеруються промені R/G/B під 60 градусів"
        ],
        "implementation_steps": ["Додати PrismSplitterComponent", "Оновити RayTraceSystem"],
        "test_plan": ["Перевірка max_bounces = 8"],
    },
    ensure_ascii=False,
)

GOOD = json.dumps(
    {
        "task_key": "JL-24",
        "branch_name": "feat/jl-24-prism-splitter",
        "summary": "Додано Burst-безпечний PrismSplitter з обмеженням глибини променя max_bounces = 8.",
        "ecs_changes": ["Створено PrismSplitterComponent : IComponentData"],
        "level_design_changes": ["Оновлено пресет JL-24 із Par Moves = 7"],
        "csharp_snippets": "[BurstCompile]\npublic partial struct RayTraceSystem : ISystem { public void OnUpdate(ref SystemState s) {} }",
        "unity_nunit_tests": "[Test]\npublic void SplitBeam_StopsAtMaxBounces() {\n    Assert.LessOrEqual(8, 8);\n}",
        "level_preset_json": json.dumps({"levelId": "JL-24", "parMoves": 7, "maxBounces": 8}),
        "assumptions": ["[[Призми дисперсії та розщеплення світлових пучків#Принцип розщеплення променів]]"],
    },
    ensure_ascii=False,
)

BAL = json.dumps(
    {
        "verdict": "approve",
        "optics_integrity_score": 5,
        "balance_score": 5,
        "issues": [],
        "required_fixes": [],
    }
)

QA = json.dumps(
    {
        "verdict": "approve",
        "burst_safety_score": 5,
        "test_coverage_score": 5,
        "missing_scenarios": [],
        "required_fixes": [],
    }
)
