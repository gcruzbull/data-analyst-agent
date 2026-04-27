# This module defines the OllamaLLM class, which implements the LLMInterface using the Ollama API.
"""
Implementación Ollama de la interfaz LLM.

Para desarrollo local sin AWS. Ollama 0.4+ soporta tool-use con los modelos
recientes (llama3.1, llama3.2). En modelos antiguos (llama3 base) el tool-use
no funcionará bien y conviene cambiar a llama3.1 o superior.
"""
from __future__ import annotations

import logging
from typing import Any

import ollama

from src.config.settings import get_settings
from src.llm.llm_interface import LLMInterface, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OllamaLLM(LLMInterface):
    def __init__(self, model: str | None = None, base_url: str | None = None):
        s = get_settings()
        self.model = model or s.ollama_model
        self.client = ollama.Client(host=base_url or s.ollama_base_url)

    @staticmethod
    def _to_ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Aplana mensajes Anthropic → formato Ollama.
        Ollama trata tool_result como un message role="tool".
        """
        out: list[dict[str, Any]] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue

            text_buf: list[str] = []
            tool_calls_buf: list[dict[str, Any]] = []

            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text_buf.append(block["text"])
                elif btype == "tool_use":
                    tool_calls_buf.append({
                        "function": {"name": block["name"], "arguments": block["input"]}
                    })
                elif btype == "tool_result":
                    tr = block["content"]
                    tr_text = tr if isinstance(tr, str) else "\n".join(b.get("text", "") for b in tr)
                    out.append({"role": "tool", "content": tr_text})

            if text_buf or tool_calls_buf:
                m: dict[str, Any] = {"role": role, "content": "".join(text_buf)}
                if tool_calls_buf:
                    m["tool_calls"] = tool_calls_buf
                out.append(m)

        return out

    @staticmethod
    def _to_ollama_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        ollama_messages = self._to_ollama_messages(messages)
        if system:
            ollama_messages = [{"role": "system", "content": system}, *ollama_messages]

        kwargs: dict[str, Any] = {"model": self.model, "messages": ollama_messages}
        if tools:
            kwargs["tools"] = self._to_ollama_tools(tools)

        response = self.client.chat(**kwargs)
        message = response["message"]

        tool_calls: list[ToolCall] = []
        for i, tc in enumerate(message.get("tool_calls") or []):
            fn = tc["function"]
            tool_calls.append(
                ToolCall(id=f"ollama_tc_{i}", name=fn["name"], input=fn.get("arguments", {}))
            )

        stop_reason = "tool_use" if tool_calls else "end_turn"

        return LLMResponse(
            text=message.get("content", ""),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=dict(response),
        )