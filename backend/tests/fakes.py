"""Doble de prueba del cliente LLM: permite guionar respuestas sin llamar a Anthropic."""
from __future__ import annotations

from app.ai.client import LLMClient, LLMResponse


class FakeLLMClient(LLMClient):
    def __init__(self, scripted_responses: list[LLMResponse]) -> None:
        self._responses = list(scripted_responses)
        self.calls: list[dict] = []

    def create_message(self, *, system, messages, tools) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self._responses:
            return LLMResponse(text="(sin más respuestas guionadas)")
        return self._responses.pop(0)
