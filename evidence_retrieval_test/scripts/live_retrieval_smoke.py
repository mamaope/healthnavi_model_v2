from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

from evidence_retrieval_test.src.services.citation_formatter import format_citations
from evidence_retrieval_test.src.services.evidence_search_service import EvidenceSearchService


DEFAULT_QUESTIONS = [
    "treatment of malaria in a 2 year old child in Uganda",
    "severe pneumonia management in a 3 year old in Zambia",
    "hypertension treatment in pregnancy in Uganda",
    "neonatal sepsis antibiotics in Zambia",
    "acute asthma exacerbation management in a child in Uganda",
    "snake bite management in rural Zambia",
    "postpartum hemorrhage management Uganda",
    "diabetes foot infection treatment in Zambia",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run local live-evidence retrieval smoke tests."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=6,
        help="Number of evidence items to show per query.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Run only the first N default questions. 0 means all.",
    )
    parser.add_argument(
        "--questions-file",
        type=Path,
        help="Optional newline-delimited questions file.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to write machine-readable results.",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    questions = _load_questions(args.questions_file)
    if args.limit > 0:
        questions = questions[: args.limit]

    service = EvidenceSearchService()
    results = []
    started_at = time.perf_counter()

    print("Live evidence retrieval smoke test")
    print(f"Questions: {len(questions)} | top_k={args.top_k}")
    print(
        "Providers: "
        f"semantic_scholar={os.getenv('ENABLE_SEMANTIC_SCHOLAR', 'true')} "
        f"official_apis={os.getenv('ENABLE_OFFICIAL_HEALTH_APIS', 'true')} "
        f"crawl4ai={os.getenv('ENABLE_CRAWL4AI', 'true')} "
        f"crawl4ai_browser={os.getenv('ENABLE_CRAWL4AI_BROWSER', 'false')}"
    )

    for index, question in enumerate(questions, start=1):
        print("\n" + "=" * 92)
        print(f"{index}. {question}")
        query_started_at = time.perf_counter()
        result = service.search(question, top_k=args.top_k)
        elapsed = round((time.perf_counter() - query_started_at) * 1000, 1)
        citations = format_citations(result.items)
        source_counts = _source_counts(result.items)
        local_count = sum(1 for item in result.items if _is_local_or_regional(item))

        print(f"Total: {elapsed} ms | results={len(result.items)} | local/regional={local_count}")
        print(f"Source mix: {source_counts or 'none'}")
        if result.provider_errors:
            print("Provider warnings:")
            for warning in result.provider_errors:
                print(f"  - {_one_line(warning)}")

        for citation in citations:
            item = result.items[int(citation["number"]) - 1]
            local_marker = " local" if _is_local_or_regional(item) else ""
            print(
                f"  [{citation['number']}]{local_marker} "
                f"{citation['source_label']} | {citation['year'] or 'n.d.'} | "
                f"score={item.final_score if item.final_score is not None else 'n/a'}"
            )
            print(f"      {citation['title']}")
            print(f"      {citation['url']}")

        results.append(
            {
                "question": question,
                "elapsed_ms": elapsed,
                "timings_ms": result.timings_ms,
                "provider_errors": result.provider_errors,
                "source_counts": source_counts,
                "local_or_regional_results": local_count,
                "items": result.model_dump(mode="json")["items"],
            }
        )

    total_elapsed = round((time.perf_counter() - started_at) * 1000, 1)
    totals = [result["elapsed_ms"] for result in results]
    print("\n" + "=" * 92)
    print("Summary")
    print(f"Total elapsed: {total_elapsed} ms")
    if totals:
        print(f"Median/query: {round(statistics.median(totals), 1)} ms")
        print(f"Max/query: {round(max(totals), 1)} ms")
    print(
        f"Queries with local/regional evidence: "
        f"{sum(1 for result in results if result['local_or_regional_results'] > 0)}/{len(results)}"
    )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote JSON results to {args.json_out}")


def _load_questions(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_QUESTIONS
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _source_counts(items) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = getattr(item.source, "value", str(item.source))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _is_local_or_regional(item) -> bool:
    haystack = " ".join(
        str(value or "")
        for value in (
            item.title,
            item.snippet,
            item.abstract,
            item.journal_or_publisher,
            item.url,
        )
    ).lower()
    return any(
        marker in haystack
        for marker in (
            "uganda",
            "ugandan",
            "zambia",
            "zambian",
            "africa",
            "african",
            "health.go.ug",
            "cphl.go.ug",
            "africacdc.org",
            "platform.who.int",
        )
    )


def _one_line(value: str, max_len: int = 240) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= max_len else f"{clean[: max_len - 3]}..."


if __name__ == "__main__":
    main()
