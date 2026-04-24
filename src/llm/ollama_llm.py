# This module defines the OllamaLLM class, which implements the LLMInterface using the Ollama API.

import ollama
from src.llm.llm_interface import LLMInterface
# from langchain_community.chat_models import ChatOllama
from src.config.settings import OLLAMA_MODEL


class OllamaLLM(LLMInterface):

    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model

    def generate(self, prompt: str) -> str:

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]