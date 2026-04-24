# This file defines a factory function to get the appropriate LLM implementation based on the configuration.
# It imports the necessary LLM classes and checks the LLM_PROVIDER setting to return the correct instance.

from src.config.settings import LLM_PROVIDER
from src.llm.ollama_llm import OllamaLLM
from src.llm.bedrock_llm import BedrockLLM


def get_llm():

    if LLM_PROVIDER == "ollama":
        return OllamaLLM()

    if LLM_PROVIDER == "bedrock":
        return BedrockLLM()

    raise ValueError("Invalid LLM provider")