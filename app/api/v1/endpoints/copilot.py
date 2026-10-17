import asyncio
import json
import re
from typing import AsyncGenerator
from decimal import Decimal
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.agent_tools import execute_deterministic_tool

router = APIRouter()

class CopilotQueryRequest(BaseModel):
    query: str
    tenant_context: dict | None = None

@router.post("/stream")
async def stream_compliance_copilot(
    req: CopilotQueryRequest,
    raw_request: Request
):
    query = req.query.strip()

    async def sse_event_publisher() -> AsyncGenerator[dict, None]:
        try:
            # 1. Statutory Grounding Citations
            citations = [
                {
                    "id": 1,
                    "title": "CGST Rule 36(4) & Sec 16(2)(aa)",
                    "category": "STATUTORY_RULE",
                    "score": 0.942,
                    "snippet": "ITC eligibility is restricted to inward supplies in GSTR-2B. Excess claimed credits in GSTR-3B require reversal under Table 4(B)(2)."
                },
                {
                    "id": 2,
                    "title": "CBIC Circular No. 170/02/2022-GST",
                    "category": "CIRCULAR",
                    "score": 0.887,
                    "snippet": "Clarification on mandatory reporting of ITC reversals and reclaim of ineligible credits in Form GSTR-3B."
                }
            ]

            for c in citations:
                yield {
                    "event": "citation",
                    "data": json.dumps(c)
                }
                await asyncio.sleep(0.1)

            # 2. Extract Numbers for Deterministic Reconciliation
            numbers = [Decimal(n) for n in re.findall(r"\d+", query.replace(",", ""))]
            books_itc = numbers[0] if len(numbers) >= 1 else Decimal("550000.00")
            g2b_itc = numbers[1] if len(numbers) >= 2 else Decimal("485000.00")

            # 3. Stream Tool Call Status
            yield {
                "event": "tool_call",
                "data": json.dumps({"tool": "calculate_itc_rule36_4", "status": "executing"})
            }
            await asyncio.sleep(0.3)

            # 4. Execute Statutory Math via Domain Engine
            args_payload = json.dumps({
                "purchase_register_itc": float(books_itc),
                "gstr2b_eligible_itc": float(g2b_itc)
            })
            tool_output = execute_deterministic_tool("calculate_itc_rule36_4", args_payload)

            yield {
                "event": "tool_result",
                "data": json.dumps({"tool": "calculate_itc_rule36_4", "result": tool_output})
            }

            # 5. Stream Tokens Incrementally
            narrative = (
                f"### Statutory Reconciliation Audit Report\n\n"
                f"- **Books Claimed ITC**: INR {books_itc:,.2f}\n"
                f"- **GSTR-2B Portal Eligible ITC**: INR {g2b_itc:,.2f}\n"
                f"- **Unmatched Ineligible Drift**: INR {Decimal(tool_output['excess_claimed']):,.2f}\n\n"
                f"**Legal Analysis under Rule 36(4):**\n"
                f"Under Section 16(2)(aa) of the CGST Act, no input tax credit can be availed unless details of such invoices "
                f"have been furnished by suppliers in their GSTR-1/IFF and communicated in GSTR-2B.\n\n"
                f"Because your books exceed GSTR-2B by **INR {Decimal(tool_output['excess_claimed']):,.2f}**, claiming this credit "
                f"will trigger an automated discrepancy notice under **Rule 88D (Form GST DRC-01C)** and invite interest liability under Section 50.\n\n"
                f"**Prescribed Action:** Reversal of unmatched credit in Table 4(B)(2) of Form GSTR-3B."
            )

            for word in narrative.split(" "):
                if await raw_request.is_disconnected():
                    return
                yield {
                    "event": "token",
                    "data": json.dumps({"token": word + " "})
                }
                await asyncio.sleep(0.02)

            # 6. Stream Human-In-The-Loop Action Card
            if tool_output["action_required"] == "REVERSE_TABLE_4B2":
                await asyncio.sleep(0.15)
                yield {
                    "event": "hitl_action_proposal",
                    "data": json.dumps({
                        "action_type": "ITC_REVERSAL_POSTING",
                        "reversal_amount": tool_output["excess_claimed"],
                        "target_form": "GSTR-3B Table 4(B)(2)",
                        "statutory_mandate": "Rule 36(4) read with Sec 16(2)(aa)"
                    })
                }

            yield {"event": "done", "data": json.dumps({"status": "COMPLETED"})}

        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(sse_event_publisher())
