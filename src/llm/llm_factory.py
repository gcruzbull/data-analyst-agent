# This file defines a factory function to get the appropriate LLM implementation based on the configuration.
# It imports the necessary LLM classes and checks the LLM_PROVIDER setting to return the correct instance.

"""Factory para resolver el provider del LLM según configuración."""
from __future__ import annotations

from src.config.settings import get_settings
from src.llm.bedrock_llm import BedrockLLM
from src.llm.llm_interface import LLMInterface
from src.llm.ollama_llm import OllamaLLM


def get_llm() -> LLMInterface:
    provider = get_settings().llm_provider.lower()

    if provider == "ollama":
        return OllamaLLM()
    if provider == "bedrock":
        return BedrockLLM()

    raise ValueError(f"LLM_PROVIDER inválido: {provider!r}. Usa 'ollama' o 'bedrock'.")