import os
from typing import Any, AsyncGenerator, Dict, List, Type, TypeVar
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel
from app.ports.llm_port import LLMClientPort

T = TypeVar("T", bound=BaseModel)

class InstructorLLMAdapter(LLMClientPort):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        self.raw_client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY", "mock-key"))
        self.instructor_client = instructor.from_openai(self.raw_client)
        self.model = model
        self.embedding_model = "text-embedding-3-small"

    async def generate_embedding(self, text: str) -> list[float]:
        resp = await self.raw_client.embeddings.create(
            input=[text.replace("\n", " ")],
            model=self.embedding_model
        )
        return resp.data[0].embedding

    async def extract_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = "You are a statutory compliance extraction AI."
    ) -> T:
        return await self.instructor_client.chat.completions.create(
            model=self.model,
            response_model=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

    async def stream_reasoning_and_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str = ""
    ) -> AsyncGenerator[dict[str, Any], None]:
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        response = await self.raw_client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            tools=tools if tools else None,
            stream=True,
            temperature=0.1
        )

        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield {"type": "token", "content": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    yield {
                        "type": "tool_call",
                        "tool_id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
