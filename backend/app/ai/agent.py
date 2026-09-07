"""Loop del agente de IA con tool calling y niveles de confirmación.

Ver docs/architecture.md §4 y docs/ai-tools.md para el diseño. Puntos clave de esta
implementación:

- El LLM solo puede pedir ejecutar una tool por nombre; el código decide si se ejecuta de
  inmediato, se pide confirmación, o se rechaza por falta de permisos.
- La memoria conversacional persiste en ``conversation_messages`` (base de datos), no en el
  modelo — se reconstruye en cada mensaje nuevo.
- Ninguna escritura en la base de datos ocurre fuera de ``app/services/*``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import AnthropicLLMClient, LLMClient
from app.ai.prompts import SYSTEM_PROMPT
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.permissions import has_permission
from app.models.conversation_message import ConversationMessage, MessageRole
from app.models.pending_action import PendingAction, PendingActionStatus
from app.models.user import User
from app.tools.registry import get_tool, llm_schemas_for_role
from app.tools.serialization import to_jsonable

_AFFIRMATIVE_EXACT = {
    "si", "sí", "dale", "ok", "okay", "confirmo", "correcto", "listo", "de acuerdo", "ya", "obvio",
}
_NEGATIVE_EXACT = {"no", "cancela", "cancelar", "para", "detente", "mejor no"}


def _is_affirmative(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in _AFFIRMATIVE_EXACT or normalized.startswith(("si ", "sí ", "dale"))


def _is_negative(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in _NEGATIVE_EXACT or normalized.startswith("no ")


class AgentSession:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._settings = get_settings()
        self._llm = llm_client or AnthropicLLMClient()

    # ------------------------------------------------------------------ público

    def handle_message(self, db: Session, user: User, text: str) -> str:
        pending = self._get_pending_action(db, user)
        if pending is not None:
            return self._resolve_pending(db, user, pending, text)
        return self._run_agent_loop(db, user, text)

    # ------------------------------------------------------------------ historial

    def _save_message(self, db: Session, user: User, role: MessageRole, content: str) -> None:
        db.add(ConversationMessage(user_id=user.id, role=role, content=content))
        db.flush()

    def _load_history(self, db: Session, user: User) -> list[dict[str, Any]]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.user_id == user.id, ConversationMessage.role != MessageRole.TOOL)
            .order_by(ConversationMessage.created_at.desc())
            .limit(self._settings.conversation_history_length)
        )
        rows = list(reversed(db.execute(stmt).scalars().all()))
        return [{"role": row.role.value, "content": row.content} for row in rows]

    def _get_pending_action(self, db: Session, user: User) -> PendingAction | None:
        stmt = (
            select(PendingAction)
            .where(PendingAction.user_id == user.id, PendingAction.status == PendingActionStatus.PENDIENTE)
            .order_by(PendingAction.created_at.desc())
        )
        return db.execute(stmt).scalars().first()

    # ------------------------------------------------------------------ confirmación pendiente

    def _resolve_pending(self, db: Session, user: User, pending: PendingAction, text: str) -> str:
        self._save_message(db, user, MessageRole.USER, text)

        if _is_negative(text):
            pending.status = PendingActionStatus.CANCELADA
            pending.resolved_at = datetime.now(timezone.utc)
            db.flush()
            reply = "Listo, no hice ese cambio."
            self._save_message(db, user, MessageRole.ASSISTANT, reply)
            return reply

        if _is_affirmative(text):
            reply = self._execute_pending(db, user, pending)
            self._save_message(db, user, MessageRole.ASSISTANT, reply)
            return reply

        # Ni confirmación ni cancelación explícita: se descarta la acción pendiente y se
        # procesa el mensaje como uno nuevo (simplificación documentada en docs/ai-tools.md).
        pending.status = PendingActionStatus.EXPIRADA
        pending.resolved_at = datetime.now(timezone.utc)
        db.flush()
        return self._run_agent_loop(db, user, text, save_user_message=False)

    def _execute_pending(self, db: Session, user: User, pending: PendingAction) -> str:
        tool_def = get_tool(pending.tool_name)
        if tool_def is None:
            pending.status = PendingActionStatus.EXPIRADA
            pending.resolved_at = datetime.now(timezone.utc)
            db.flush()
            return "Esa acción ya no está disponible. ¿Puedes repetir lo que necesitas?"

        try:
            validated = tool_def.input_model.model_validate(pending.tool_input)
            result_payload = tool_def.handler(db, user, validated)
            pending.status = PendingActionStatus.CONFIRMADA
        except (DomainError, ValidationError) as exc:
            result_payload = {"error": str(exc)}
            pending.status = PendingActionStatus.CANCELADA

        pending.resolved_at = datetime.now(timezone.utc)
        db.flush()
        return self._summarize_result(pending.summary_for_user, result_payload)

    def _summarize_result(self, summary_for_user: str, result_payload: dict) -> str:
        if isinstance(result_payload, dict) and "error" in result_payload:
            prompt = (
                "No se pudo completar la siguiente acción que el usuario acababa de confirmar: "
                f"{summary_for_user}\nMotivo: {result_payload['error']}\n"
                "Explícale esto brevemente en español, sin tecnicismos."
            )
        else:
            prompt = (
                f"El usuario confirmó esta acción: {summary_for_user}\n"
                f"Resultado: {json.dumps(to_jsonable(result_payload), ensure_ascii=False)}\n"
                "Confírmale brevemente que se realizó, en español, tono asistente interno de Jacobea."
            )
        response = self._llm.create_message(
            system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}], tools=[]
        )
        return response.text or "Listo, hice lo que confirmaste."

    # ------------------------------------------------------------------ loop principal

    def _build_confirmation_summary(self, tool_def, validated) -> str:
        datos = validated.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        detalle = ", ".join(f"{k}: {v}" for k, v in datos.items()) or "(sin más detalles)"
        return (
            f"Voy a hacer lo siguiente: {tool_def.description}\nDetalles: {detalle}\n"
            "¿Confirmas? Responde 'sí' o 'no'."
        )

    def _run_agent_loop(self, db: Session, user: User, text: str, save_user_message: bool = True) -> str:
        if save_user_message:
            self._save_message(db, user, MessageRole.USER, text)

        working_messages = self._load_history(db, user)
        tools_schema = llm_schemas_for_role(user.rol)

        final_text: str | None = None

        for _ in range(self._settings.max_tool_iterations):
            response = self._llm.create_message(system=SYSTEM_PROMPT, messages=working_messages, tools=tools_schema)

            if not response.wants_tool_call:
                final_text = response.text or "Listo."
                break

            assistant_content: list[dict[str, Any]] = []
            if response.text:
                assistant_content.append({"type": "text", "text": response.text})
            for call in response.tool_calls:
                assistant_content.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
                )
            working_messages.append({"role": "assistant", "content": assistant_content})

            confirmation_reply: str | None = None
            tool_result_blocks: list[dict[str, Any]] = []

            for call in response.tool_calls:
                result_payload = self._dispatch_tool_call(db, user, call.name, call.input)

                if result_payload.get("__needs_confirmation__"):
                    confirmation_reply = result_payload["summary"]
                    break

                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps(to_jsonable(result_payload), ensure_ascii=False),
                    }
                )

            if confirmation_reply is not None:
                final_text = confirmation_reply
                break

            working_messages.append({"role": "user", "content": tool_result_blocks})
        else:
            final_text = (
                "Estoy teniendo problemas para completar esa solicitud. ¿Puedes darme más "
                "detalles o intentarlo de nuevo?"
            )

        final_text = final_text or "Listo."
        self._save_message(db, user, MessageRole.ASSISTANT, final_text)
        return final_text

    def _dispatch_tool_call(self, db: Session, user: User, tool_name: str, tool_input: dict[str, Any]) -> dict:
        """Único punto donde se decide si una tool se ejecuta, se pospone para confirmación,
        o se rechaza. Esto es código, no una instrucción de prompt (ver docs/architecture.md)."""
        tool_def = get_tool(tool_name)
        if tool_def is None:
            return {"error": f"Herramienta desconocida: {tool_name}"}

        if tool_def.required_permission is not None and not has_permission(user.rol, tool_def.required_permission):
            return {"error": "No tienes permiso para usar esta función."}

        try:
            validated = tool_def.input_model.model_validate(tool_input)
        except ValidationError as exc:
            return {"error": f"Los datos entregados no son válidos: {exc.errors()}"}

        level = tool_def.confirmation_level_for(validated, user)
        if level >= 2:
            summary = self._build_confirmation_summary(tool_def, validated)
            pending = PendingAction(
                user_id=user.id,
                tool_name=tool_def.name,
                tool_input=validated.model_dump(mode="json", exclude_unset=True),
                summary_for_user=summary,
            )
            db.add(pending)
            db.flush()
            return {"__needs_confirmation__": True, "summary": summary}

        try:
            return tool_def.handler(db, user, validated)
        except DomainError as exc:
            return {"error": str(exc)}
