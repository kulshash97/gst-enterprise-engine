from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMClientPort(ABC):
    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate high-dimensional vector embeddings."""
        pass

    @abstractmethod
    async def extract_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = ""
    ) -> T:
        """Enforce Pydantic schema validation using structured model parsing."""
        pass

    @abstractmethod
    async def stream_reasoning_and_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str = ""
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chunks, tool dispatch calls, and reasoning tokens."""
        pass
