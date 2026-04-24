# This file defines the LLMInterface and its implementations for different language models.
# It also includes a factory function to get the appropriate LLM based on settings.

from abc import ABC, abstractmethod

# Generate a abstract base class for LLMInterface with a generate method that takes a prompt and returns a response.
class LLMInterface(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM based on the prompt.
        """
        pass

