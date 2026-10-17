import json
from decimal import Decimal
from pydantic import BaseModel, Field
from app.services.tax_engine import compute_statutory_taxes, round_paisa

class ITCMismatchInput(BaseModel):
    purchase_register_itc: Decimal = Field(..., description="ITC claimed in books (INR)")
    gstr2b_eligible_itc: Decimal = Field(..., description="ITC visible in GSTR-2B portal (INR)")

class StatutoryTaxCalcInput(BaseModel):
    taxable_value: Decimal
    hsn_rate: Decimal
    is_interstate: bool

AGENT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_itc_rule36_4",
            "description": "Calculates allowable ITC under Rule 36(4) and identifies reversal requirements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purchase_register_itc": {"type": "number", "description": "ITC in Books"},
                    "gstr2b_eligible_itc": {"type": "number", "description": "ITC in 2B"}
                },
                "required": ["purchase_register_itc", "gstr2b_eligible_itc"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_statutory_tax",
            "description": "Computes exact CGST/SGST/IGST paisa distribution without float drift.",
            "parameters": {
                "type": "object",
                "properties": {
                    "taxable_value": {"type": "number"},
                    "hsn_rate": {"type": "number"},
                    "is_interstate": {"type": "boolean"}
                },
                "required": ["taxable_value", "hsn_rate", "is_interstate"]
            }
        }
    }
]

def execute_deterministic_tool(name: str, arguments_json: str) -> dict:
    args = json.loads(arguments_json)
    if name == "calculate_itc_rule36_4":
        pr_itc = round_paisa(Decimal(str(args["purchase_register_itc"])))
        g2b_itc = round_paisa(Decimal(str(args["gstr2b_eligible_itc"])))
        
        ineligible_drift = pr_itc - g2b_itc
        requires_reversal = ineligible_drift > Decimal("0.00")
        
        return {
            "status": "SUCCESS",
            "books_itc": str(pr_itc),
            "gstr2b_itc": str(g2b_itc),
            "excess_claimed": str(ineligible_drift if requires_reversal else Decimal("0.00")),
            "action_required": "REVERSE_TABLE_4B2" if requires_reversal else "ELIGIBLE_CLAIM",
            "statutory_note": "Rule 36(4) read with Section 16(2)(aa) mandates reversal of unmatched credits."
        }
    elif name == "compute_statutory_tax":
        res = compute_statutory_taxes(
            taxable_value=Decimal(str(args["taxable_value"])),
            hsn_rate=Decimal(str(args["hsn_rate"])),
            is_interstate=bool(args["is_interstate"])
        )
        return {k: str(v) for k, v in res.items()}
    raise ValueError(f"Unknown tool: {name}")
