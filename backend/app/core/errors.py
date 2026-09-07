"""Excepciones de dominio compartidas entre la API REST y las tools de IA.

Se mapean a HTTP en ``app/api/deps.py`` y a mensajes de error estructurados para el LLM en
``app/tools/registry.py`` — un mismo error, dos representaciones.
"""
from __future__ import annotations


class DomainError(Exception):
    """Error de negocio esperable (no un bug)."""


class PermissionDeniedError(DomainError):
    def __init__(self, message: str = "No tienes permiso para realizar esta acción."):
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, message: str = "No encontrado."):
        super().__init__(message)


class ValidationDomainError(DomainError):
    pass
