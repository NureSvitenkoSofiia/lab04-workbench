"""Контракти даних (Pydantic-схеми) для мультиагентної системи jarlight-feature-sdlc."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FeaturePlanSpec(BaseModel):
    """Структурована оцінка GDD-запиту та план змін у Unity-проєкті JarLight."""

    task_key: str = Field(
        description="Ключ задачі з беклогу JarLight (наприклад, JL-24 або JL-NEW)"
    )
    title: str = Field(
        min_length=4,
        max_length=120,
        description="Коротка інженерна назва ігрової фічі або механіки",
    )
    readiness_status: Literal["ready", "needs_clarification"] = Field(
        description="Статус готовності опису до конструювання в Unity ECS"
    )
    readiness_score: int = Field(
        ge=1,
        le=5,
        description="Оцінка повноти оптичних та архітектурних вимог від 1 до 5",
    )
    clarification_questions: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Список уточнювальних запитань до геймдизайнера, якщо опис неповний",
    )
    affected_systems: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Підсистеми JarLight (Optics, Mechanics, ECS, LevelDesign, UI, Audio)",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        max_length=7,
        description="Перевірювані критерії приймання у форматі Given/When/Then",
    )
    implementation_steps: list[str] = Field(
        default_factory=list,
        max_length=7,
        description="Покроковий план змін у C# ECS, ScriptableObjects та конфігах рівнів",
    )
    test_plan: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="План перевірки оптики, балансу Par Moves та тестів Unity Test Framework",
    )


class UnityFeatureBundle(BaseModel):
    """Вихід інженера Unity: C# ECS-зміни, конфіг рівня JSON і набір NUnit-тестів."""

    task_key: str = Field(description="Ключ задачі JarLight")
    branch_name: str = Field(
        min_length=5,
        max_length=80,
        description="Назва гілки виду feat/jl-24-prism-splitter",
    )
    summary: str = Field(
        min_length=10,
        max_length=450,
        description="Стислий підсумок змін в архітектурі Unity ECS і механіках гри",
    )
    ecs_changes: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Перелік змін C# компонентів IComponentData та систем ISystem / EventBus",
    )
    level_design_changes: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Зміни для ScriptableObjects, гексагональної сітки та норми Par Moves",
    )
    csharp_snippets: str = Field(
        default="",
        max_length=4000,
        description="Ключовий фрагмент C# коду для Unity ECS або Burst-системи",
    )
    unity_nunit_tests: str = Field(
        default="",
        max_length=4000,
        description="Набір EditMode/PlayMode тестів C# NUnit з [Test]/[UnityTest] і Assert",
    )
    level_preset_json: str = Field(
        default="{}",
        max_length=2500,
        description="Валідний JSON пресет демонстраційного рівня або ScriptableObject",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Припущення та посилання на фрагменти бази знань [[Нотатка#Розділ]]",
    )


class GameBalanceReviewReport(BaseModel):
    """Ревью ігрового балансу, законів оптики та кривої складності JarLight."""

    verdict: Literal["approve", "revise"] = Field(
        description="Підсумковий вердикт ревю оптики та геймдизайну"
    )
    optics_integrity_score: int = Field(
        ge=1, le=5, description="Коректність фізики світла, Снелла й моделі RGB (1..5)"
    )
    balance_score: int = Field(
        ge=1, le=5, description="Узгодженість з Par Moves, банками та кристалами (1..5)"
    )
    issues: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Виявлені дефекти оптики чи дисбаланс",
    )
    required_fixes: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Конкретні виправлення при вердикті revise",
    )


class UnityEcsQaReport(BaseModel):
    """Ревью продуктивності Unity ECS/Burst і достатності NUnit-тестів."""

    verdict: Literal["approve", "revise"] = Field(
        description="Підсумковий вердикт ревю Unity QA"
    )
    burst_safety_score: int = Field(
        ge=1, le=5, description="Безпека коду для Burst/ECS без алокацій і Find (1..5)"
    )
    test_coverage_score: int = Field(
        ge=1, le=5, description="Повнота позитивних і граничних NUnit-тестів (1..5)"
    )
    missing_scenarios: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Пропущені граничні випадки (max_bounces, переповнення банок тощо)",
    )
    required_fixes: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Обов язкові правки для C# тестів або пресету рівня",
    )


class SoloFeatureResult(BaseModel):
    """Єдина схема результату для базової лінії (один агент без команди)."""

    task_key: str = Field(description="Ключ задачі JarLight")
    title: str = Field(description="Назва фічі")
    readiness_status: Literal["ready", "needs_clarification"] = Field(
        description="Готовність задачі"
    )
    clarification_questions: list[str] = Field(
        default_factory=list, description="Питання уточнення за потреби"
    )
    branch_name: str = Field(description="Назва гілки Git")
    ecs_changes: list[str] = Field(
        default_factory=list, description="Зміни C# ECS"
    )
    level_design_changes: list[str] = Field(
        default_factory=list, description="Зміни левел-дизайну / ScriptableObject"
    )
    csharp_snippets: str = Field(default="", description="Сніпет C# коду")
    unity_nunit_tests: str = Field(default="", description="NUnit тести C#")
    level_preset_json: str = Field(default="{}", description="JSON пресету рівня")
    assumptions: list[str] = Field(
        default_factory=list, description="Припущення"
    )
