from abc import ABC, abstractmethod
from typing import Any, List
from pydantic import BaseModel

class GroundingChunk(BaseModel):
    id: int
    title: str
    category: str
    chunk_text: str
    score: float
    metadata: dict[str, Any]

class KnowledgeRepositoryPort(ABC):
    @abstractmethod
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 4,
        alpha: float = 0.5
    ) -> list[GroundingChunk]:
        """Perform Reciprocal Rank Fusion / hybrid cosine similarity + full-text search."""
        pass
