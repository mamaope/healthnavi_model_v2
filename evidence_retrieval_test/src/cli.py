from __future__ import annotations

import argparse
import json

from evidence_retrieval_test.src.services.citation_formatter import (
    build_llm_context,
    format_citations,
)
from evidence_retrieval_test.src.services.evidence_search_service import (
    EvidenceSearchService,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve citation-ready medical evidence.")
    parser.add_argument("question", help="Clinical question to search evidence for.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence items to return.")
    args = parser.parse_args()

    service = EvidenceSearchService()
    result = service.search(args.question, top_k=args.top_k)
    payload = {
        **result.model_dump(mode="json"),
        "citations": format_citations(result.items),
        "llm_context": build_llm_context(result.items),
    }

    print(json.dumps(payload, indent=2))
    if result.timings_ms:
        print("\nTimings")
        for name, elapsed_ms in result.timings_ms.items():
            print(f"{name}: {elapsed_ms} ms")
    print("\nEvidence list")
    for index, item in enumerate(result.items, start=1):
        year = item.year or item.publication_date or "n.d."
        print(f"[{index}] {item.title} ({year})")
        print(f"    {item.url}")
        if item.final_score is not None:
            print(f"    score={item.final_score}")


if __name__ == "__main__":
    main()
