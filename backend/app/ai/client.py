"""Cliente LLM desacoplado.

``AgentSession`` (app/ai/agent.py) solo conoce ``LLMClient`` y las dataclasses de este
módulo — nunca importa el SDK de Anthropic directamente. Esto permite cambiar de proveedor de
LLM (OpenAI, otro) implementando una nueva clase que cumpla ``LLMClient`` sin tocar el resto
del sistema, tal como pide el brief.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings


@dataclass
class ToolCallRequest:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    stop_reason: str = "end_turn"

    @property
    def wants_tool_call(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(ABC):
    @abstractmethod
    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Envía la conversación al modelo y devuelve texto y/o tool calls pedidos."""


class AnthropicLLMClient(LLMClient):
    """Implementación real usando el SDK oficial de Anthropic (tool calling nativo)."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY no está configurado. El agente de IA no puede funcionar "
                "sin credenciales del LLM (ver .env.example)."
            )
        import anthropic  # import diferido: no requerido si no se usa este cliente

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def create_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=tools or None,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCallRequest(id=block.id, name=block.name, input=block.input))

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
        )
