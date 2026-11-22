"""Підмінні моделі ScriptedLlm та ToolCallingLlm для офлайн-тестів ЛР 4."""

from __future__ import annotations

import threading
from collections.abc import AsyncGenerator

from google.adk.models import LlmRequest, LlmResponse
from google.adk.models.base_llm import BaseLlm
from google.genai import types
from pydantic import Field, PrivateAttr


class ScriptedLlm(BaseLlm):
    """Видає підготовлені JSON/текстові відповіді залежно від ROLE маркера."""

    script: dict[str, list[str]] = Field(default_factory=dict)
    calls: list[str] = Field(default_factory=list)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def _detect_role(self, sys_inst: str) -> str:
        for role_key in self.script:
            if role_key in sys_inst:
                return role_key
        return "default"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        sys_inst = ""
        if llm_request.config and llm_request.config.system_instruction:
            sys_inst = str(llm_request.config.system_instruction)
        with self._lock:
            role = self._detect_role(sys_inst)
            self.calls.append(role)
            responses = self.script.get(role, ["{}"])
            payload = responses.pop(0) if len(responses) > 1 else responses[0]
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=payload)])
        )


class ToolCallingLlm(BaseLlm):
    """Спершу викликає інструменти зі списку calls, потім відповідає текстом answer."""

    calls: list[tuple[str, dict]] = Field(default_factory=list)
    answer: str = ""
    seen_tool_results: list[str] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = (
            llm_request.contents[-1].parts[0]
            if llm_request.contents and llm_request.contents[-1].parts
            else None
        )
        if last is not None and last.function_response:
            self.seen_tool_results.append(str(last.function_response.response))
        if self.calls:
            name, args = self.calls.pop(0)
            part = types.Part(function_call=types.FunctionCall(name=name, args=args))
        else:
            part = types.Part(text=self.answer)
        yield LlmResponse(content=types.Content(role="model", parts=[part]))
