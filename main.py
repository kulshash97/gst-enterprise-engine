import os
import asyncio
import json
import re
from decimal import Decimal
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.services.agent_tools import execute_deterministic_tool
from app.services.tax_engine import HSN_RATES, compute_statutory_taxes, round_paisa

settings = get_settings()

app = FastAPI(title=settings.PROJECT_NAME, version="2.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", tags=["Frontend"])
async def serve_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "ApexTax Engine API running"}

@app.get("/copilot", tags=["Frontend"])
async def serve_copilot():
    if os.path.exists("static/copilot.html"):
        return FileResponse("static/copilot.html")
    return {"message": "Copilot UI file not found."}

async def _generate_copilot_stream(query: str):
    # Statutory Citations
    citations = [
        {
            "title": "CGST Rule 36(4) & Sec 16(2)(aa)",
            "category": "STATUTORY_RULE",
            "score": 0.94,
            "snippet": "ITC eligibility is restricted to inward supplies appearing in GSTR-2B. Excess claimed credits require reversal under Table 4(B)(2)."
        },
        {
            "title": "CBIC Circular No. 170/02/2022-GST",
            "category": "CIRCULAR",
            "score": 0.89,
            "snippet": "Mandatory reporting of ITC reversals and reclaim of ineligible credits in Form GSTR-3B."
        }
    ]
    for c in citations:
        yield {"event": "citation", "data": json.dumps(c)}
        await asyncio.sleep(0.05)

    # Clean out statutory form codes (2B, 3B, 88D, etc.) before parsing financial amounts
    cleaned_query = re.sub(r'(?i)\b(2b|3b|88c|88d|01b|01c|36\(4\)|16\(2\))\b', '', query)
    nums = [Decimal(n) for n in re.findall(r"\d+", cleaned_query.replace(",", ""))]
    books_val = nums[0] if len(nums) >= 1 else Decimal("550000.00")
    g2b_val = nums[1] if len(nums) >= 2 else Decimal("485000.00")

    # Tool Execution Status Pill
    yield {"event": "tool_call", "data": json.dumps({"tool": "calculate_itc_rule36_4"})}
    await asyncio.sleep(0.2)

    tool_output = execute_deterministic_tool(
        "calculate_itc_rule36_4",
        json.dumps({"purchase_register_itc": float(books_val), "gstr2b_eligible_itc": float(g2b_val)})
    )
    yield {"event": "tool_result", "data": json.dumps({"tool": "calculate_itc_rule36_4", "result": tool_output})}

    # Word-by-Word Streaming Narrative
    text = (
        f"=== STATUTORY RECONCILIATION AUDIT ===\n\n"
        f"• Books ITC Claimed: INR {books_val:,.2f}\n"
        f"• GSTR-2B Eligible ITC: INR {g2b_val:,.2f}\n"
        f"• Unmatched Discrepancy: INR {Decimal(tool_output['excess_claimed']):,.2f}\n\n"
        f"STATUTORY MANDATE (Rule 36(4)):\n"
        f"Availing unmatched credit of INR {Decimal(tool_output['excess_claimed']):,.2f} triggers "
        f"an automated intimation in Form GST DRC-01C (Rule 88D) and interest liability under Section 50.\n\n"
        f"RECOMMENDED ACTION: Reversal in Table 4(B)(2) of Form GSTR-3B."
    )

    for chunk in text.split(" "):
        yield {"event": "token", "data": json.dumps({"token": chunk + " "})}
        await asyncio.sleep(0.015)

    if tool_output["action_required"] == "REVERSE_TABLE_4B2":
        yield {
            "event": "hitl",
            "data": json.dumps({
                "amount": tool_output["excess_claimed"],
                "rule": "Rule 36(4)"
            })
        }
    yield {"event": "done", "data": json.dumps({"status": "OK"})}

@app.post("/stream-copilot")
@app.post("/api/v1/ai/compliance-copilot/stream")
async def copilot_stream_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    return EventSourceResponse(_generate_copilot_stream(query))