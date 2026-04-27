# This file implements the BedrockLLM class, which uses Amazon Bedrock to generate responses based on prompts in production environment.
"""
Cliente Bedrock para Claude usando la Converse API.

Por qué Converse en lugar de invoke_model:
- API unificada para todos los modelos (no hay que armar el JSON específico de Anthropic).
- Tool-use nativo y serializado de forma consistente.
- Soporte directo para inference profiles (cross-region).
- Mejor manejo de stop_reason y errores.
"""
from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.config import Config

from src.config.settings import get_settings
from src.llm.llm_interface import LLMInterface, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

# This class implements the LLMInterface using Amazon Bedrock API to generate responses from the specified model.
class BedrockLLM(LLMInterface):
    def __init__(self, model_id: str | None = None, region: str | None = None):
        s = get_settings()
        self.model_id = model_id or s.bedrock_model_id
        self.region = region or s.aws_region
        self.max_tokens = s.bedrock_max_tokens
        self.temperature = s.bedrock_temperature

        # Retries automáticos para throttling. Bedrock tiene quotas estrictas.
        boto_cfg = Config(
            region_name=self.region,
            retries={"max_attempts": 5, "mode": "adaptive"},
            read_timeout=120,
            connect_timeout=10,
        )
        self.client = boto3.client("bedrock-runtime", config=boto_cfg)

    # ------------------------------------------------------------------ #
    # Conversión de formato Anthropic → Converse API
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_converse_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Transforma mensajes en formato Anthropic ({role, content}) al esquema
        de Converse: {role, content: [{text|toolUse|toolResult}]}.
        """
        converse_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Si content es un string simple, envolverlo en un bloque de texto.
            if isinstance(content, str):
                converse_messages.append(
                    {"role": role, "content": [{"text": content}]}
                )
                continue

            # Si es lista de bloques, mapear cada uno.
            blocks: list[dict[str, Any]] = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    blocks.append({"text": block["text"]})
                elif btype == "tool_use":
                    blocks.append({
                        "toolUse": {
                            "toolUseId": block["id"],
                            "name": block["name"],
                            "input": block["input"],
                        }
                    })
                elif btype == "tool_result":
                    tr_content = block["content"]
                    if isinstance(tr_content, str):
                        tr_content = [{"text": tr_content}]
                    blocks.append({
                        "toolResult": {
                            "toolUseId": block["tool_use_id"],
                            "content": tr_content,
                            "status": "error" if block.get("is_error") else "success",
                        }
                    })
            converse_messages.append({"role": role, "content": blocks})

        return converse_messages

    @staticmethod
    def _to_converse_tools(tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Tools en formato Anthropic → toolConfig de Converse."""
        return {
            "tools": [
                {
                    "toolSpec": {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": {"json": t["input_schema"]},
                    }
                }
                for t in tools
            ]
        }

    # ------------------------------------------------------------------ #
    # Llamada principal
    # ------------------------------------------------------------------ #
    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": self._to_converse_messages(messages),
            "inferenceConfig": {
                "maxTokens": self.max_tokens,
                "temperature": self.temperature,
            },
        }
        if system:
            kwargs["system"] = [{"text": system}]
        if tools:
            kwargs["toolConfig"] = self._to_converse_tools(tools)

        logger.debug("Bedrock converse request: model=%s, n_messages=%d", self.model_id, len(messages))
        response = self.client.converse(**kwargs)

        # Extraer texto y tool_calls del output normalizado.
        out_message = response["output"]["message"]
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in out_message["content"]:
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_calls.append(ToolCall(id=tu["toolUseId"], name=tu["name"], input=tu["input"]))

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.get("stopReason", ""),
            raw=response,
        )