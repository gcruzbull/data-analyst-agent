# This file defines the LLMInterface and its implementations for different language models.
# It also includes a factory function to get the appropriate LLM based on settings.

"""
Interfaz abstracta del LLM.

Mejora: A diferencia del repositorio inicial, esta interfaz expone `chat()` con soporte
para mensajes multi-turno y tool-use. Es lo mínimo que necesita un agente ReAct.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    """Representación normalizada de una llamada a herramienta solicitada por el LLM."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """Respuesta normalizada del LLM."""
    text: str                       # texto generado (puede estar vacío si solo hubo tool_use)
    tool_calls: list[ToolCall]      # tool_use blocks solicitados por el modelo
    stop_reason: str                # "end_turn" | "tool_use" | "max_tokens" | ...
    raw: dict[str, Any]             # respuesta cruda para debugging


# Generate a abstract base class for LLMInterface
class LLMInterface(ABC):
    """
    Contrato mínimo que un proveedor LLM debe cumplir para ser usado por el agente.
    """

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """
        Conversación multi-turno con tool-use opcional.

        Args:
            messages: lista de mensajes en formato Anthropic
                      [{"role": "user"|"assistant", "content": str | list[block]}]
            system: prompt de sistema
            tools: definiciones de herramientas en formato Anthropic tool-use

        Returns:
            LLMResponse normalizado.
        """
        raise NotImplementedError

