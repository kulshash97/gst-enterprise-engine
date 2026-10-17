import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from app.api.dependencies import get_current_tenant, get_db
from app.models.tenant import Tenant
from app.adapters.instructor_llm_adapter import InstructorLLMAdapter
from app.adapters.pg_knowledge_repository import PgKnowledgeRepositoryAdapter
from app.services.agent_tools import AGENT_TOOL_DEFINITIONS, execute_deterministic_tool

router = APIRouter()

class CopilotQueryRequest(BaseModel):
    query: str
    tenant_context: dict | None = None

@router.post("/stream")
async def stream_compliance_copilot(
    req: CopilotQueryRequest,
    raw_request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db = Depends(get_db)
):
    llm_adapter = InstructorLLMAdapter()
    repo = PgKnowledgeRepositoryAdapter(session=db)

    try:
        query_vec = await llm_adapter.generate_embedding(req.query)
        grounded_chunks = await repo.hybrid_search(
            query_text=req.query,
            query_vector=query_vec,
            top_k=2
        )
    except Exception:
        grounded_chunks = []

    grounding_context = "\n\n".join([
        f"[{c.title} ({c.category})]: {c.chunk_text}" for c in grounded_chunks
    ])

    system_prompt = (
        f"You are the ApexTax Statutory Compliance Copilot for Tenant GSTIN: {tenant.gstin}.\n"
        f"GROUNDING LEGAL CITATIONS:\n{grounding_context}\n\n"
        "RULES: Always call statutory tools for calculations. "
        "Quote official circulars accurately. Never make up amounts."
    )

    messages = [{"role": "user", "content": req.query}]

    async def sse_event_publisher() -> AsyncGenerator[dict, None]:
        try:
            for chunk in grounded_chunks:
                yield {
                    "event": "citation",
                    "data": json.dumps({
                        "id": chunk.id,
                        "title": chunk.title,
                        "category": chunk.category,
                        "score": round(chunk.score, 3),
                        "snippet": chunk.chunk_text[:140] + "..."
                    })
                }

            tool_call_accumulator = {}

            async for token_event in llm_adapter.stream_reasoning_and_tools(
                messages=messages,
                tools=AGENT_TOOL_DEFINITIONS,
                system_prompt=system_prompt
            ):
                if await raw_request.is_disconnected():
                    break

                if token_event["type"] == "token":
                    yield {"event": "token", "data": json.dumps({"token": token_event["content"]})}

                elif token_event["type"] == "tool_call":
                    tc_id = token_event.get("tool_id", "tc_0")
                    if tc_id not in tool_call_accumulator:
                        tool_call_accumulator[tc_id] = {
                            "name": token_event["name"],
                            "args": token_event["arguments"] or ""
                        }
                    else:
                        tool_call_accumulator[tc_id]["args"] += (token_event["arguments"] or "")

            for tc_id, data in tool_call_accumulator.items():
                yield {
                    "event": "tool_call",
                    "data": json.dumps({"tool": data["name"], "status": "executing"})
                }
                
                tool_output = execute_deterministic_tool(data["name"], data["args"])

                yield {
                    "event": "tool_result",
                    "data": json.dumps({"tool": data["name"], "result": tool_output})
                }

                if data["name"] == "calculate_itc_rule36_4" and tool_output["action_required"] == "REVERSE_TABLE_4B2":
                    yield {
                        "event": "hitl_action_proposal",
                        "data": json.dumps({
                            "action_type": "ITC_REVERSAL_POSTING",
                            "reversal_amount": tool_output["excess_claimed"],
                            "target_form": "GSTR-3B Table 4(B)(2)",
                            "statutory_mandate": "Rule 36(4)"
                        })
                    }

            yield {"event": "done", "data": json.dumps({"status": "COMPLETED"})}

        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(sse_event_publisher())
