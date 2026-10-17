from typing import List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.ports.knowledge_repository_port import GroundingChunk, KnowledgeRepositoryPort

class PgKnowledgeRepositoryAdapter(KnowledgeRepositoryPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 4,
        alpha: float = 0.5
    ) -> list[GroundingChunk]:
        vector_str = f"[{','.join(str(x) for x in query_vector)}]"
        
        sql_query = text("""
            WITH vector_matches AS (
                SELECT id, title, category, chunk_text, metadata,
                       1 - (embedding <=> :vec::vector) AS cosine_sim
                FROM statutory_knowledge_nodes
                ORDER BY embedding <=> :vec::vector
                LIMIT :limit
            ),
            text_matches AS (
                SELECT id, title, category, chunk_text, metadata,
                       ts_rank_cd(to_tsvector('english', chunk_text), plainto_tsquery('english', :q)) AS text_score
                FROM statutory_knowledge_nodes
                WHERE to_tsvector('english', chunk_text) @@ plainto_tsquery('english', :q)
                LIMIT :limit
            )
            SELECT 
                COALESCE(v.id, t.id) AS id,
                COALESCE(v.title, t.title) AS title,
                COALESCE(v.category, t.category) AS category,
                COALESCE(v.chunk_text, t.chunk_text) AS chunk_text,
                COALESCE(v.metadata, t.metadata) AS metadata,
                (:alpha * COALESCE(v.cosine_sim, 0.0) + (1.0 - :alpha) * COALESCE(t.text_score, 0.0)) AS combined_score
            FROM vector_matches v
            FULL OUTER JOIN text_matches t ON v.id = t.id
            ORDER BY combined_score DESC
            LIMIT :top_k;
        """)

        result = await self.session.execute(
            sql_query,
            {
                "vec": vector_str,
                "q": query_text,
                "limit": top_k * 2,
                "alpha": alpha,
                "top_k": top_k
            }
        )
        rows = result.mappings().all()
        return [
            GroundingChunk(
                id=row["id"],
                title=row["title"],
                category=row["category"],
                chunk_text=row["chunk_text"],
                score=float(row["combined_score"]),
                metadata=row["metadata"] or {}
            )
            for row in rows
        ]
