from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from evidence_retrieval_test.src.services.citation_formatter import (
    build_llm_context,
    format_citations,
)
from evidence_retrieval_test.src.services.evidence_search_service import (
    EvidenceSearchService,
)


app = FastAPI(title="Experimental Evidence Retrieval API")


class EvidenceSearchRequest(BaseModel):
    question: str
    top_k: int = Field(default=8, ge=1, le=25)


@app.post("/evidence/search")
def search_evidence(request: EvidenceSearchRequest) -> dict:
    service = EvidenceSearchService()
    result = service.search(request.question, top_k=request.top_k)
    return {
        "query": result.query,
        "normalized_query": result.normalized_query,
        "items": [item.model_dump(mode="json") for item in result.items],
        "citations": format_citations(result.items),
        "llm_context": build_llm_context(result.items),
        "provider_errors": result.provider_errors,
        "timings_ms": result.timings_ms,
    }
