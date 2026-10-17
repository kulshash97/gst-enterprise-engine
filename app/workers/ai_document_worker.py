import re
from decimal import Decimal
from langfuse import Langfuse
from app.workers.celery_app import celery_app
from app.adapters.instructor_llm_adapter import InstructorLLMAdapter
from app.schemas.extraction import ExtractedInvoiceDossier

langfuse = Langfuse()

def guardrail_check(raw_text: str) -> None:
    injection_patterns = [
        r"ignore previous instructions",
        r"system prompt override",
        r"bypass tax rules",
        r"drop table"
    ]
    for pattern in injection_patterns:
        if re.search(pattern, raw_text, re.IGNORECASE):
            raise ValueError(f"Security Guardrail Violation: Pattern detected: {pattern}")

@celery_app.task(name="tasks.process_unstructured_document")
def process_unstructured_document(document_text: str, tenant_id: int):
    guardrail_check(document_text)

    trace = langfuse.trace(
        name="Unstructured_Invoice_Extraction",
        user_id=f"tenant_{tenant_id}",
        metadata={"tenant_id": tenant_id}
    )

    import asyncio
    async def _extract():
        adapter = InstructorLLMAdapter()
        generation = trace.generation(
            name="instructor_pydantic_extraction",
            model="gpt-4o"
        )
        try:
            dossier: ExtractedInvoiceDossier = await adapter.extract_structured(
                prompt=f"Extract legal invoice dossier:\n\n{document_text}",
                response_model=ExtractedInvoiceDossier
            )
            generation.end(output=dossier.model_dump())
            return dossier
        except Exception as e:
            generation.end(error=str(e))
            raise e

    extracted = asyncio.run(_extract())

    return {
        "status": "PROCESSED_AND_VERIFIED",
        "invoice_number": extracted.invoice_number,
        "taxable_total": str(extracted.taxable_total),
        "grand_total": str(extracted.grand_total),
        "items_count": len(extracted.items)
    }
