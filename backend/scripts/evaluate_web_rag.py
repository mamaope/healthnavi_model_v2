from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from healthnavi.services.evidence_retrieval_adapter import generate_model_service_response


DEFAULT_CASES = Path(__file__).resolve().parents[1] / "evaluation" / "web_rag_smoke.json"


async def _run_case(case: dict, deep_search: bool) -> dict:
    answer, complete, prompt_type, followups = await generate_model_service_response(
        str(case["question"]),
        "",
        "",
        deep_search,
        None,
    )
    answer_text = answer.lower()
    urls = re.findall(r"https?://[^\s)]+", answer)
    hosts = {urlparse(url).netloc.lower().removeprefix("www.") for url in urls}
    expected_terms = [str(term).lower() for term in case.get("expected_terms", [])]
    preferred_domains = [str(domain).lower() for domain in case.get("preferred_domains", [])]
    missing_terms = [term for term in expected_terms if term not in answer_text]
    matched_domains = [
        domain
        for domain in preferred_domains
        if any(host == domain or host.endswith(f".{domain}") for host in hosts)
    ]
    inline_markers = re.findall(r"\[\[?\d+\]?\]\(", answer)
    return {
        "id": case.get("id"),
        "complete": complete,
        "prompt_type": prompt_type,
        "passed": bool(inline_markers) and not missing_terms and bool(matched_domains),
        "missing_terms": missing_terms,
        "matched_domains": matched_domains,
        "url_count": len(urls),
        "followup_count": len(followups),
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run Empirico web-RAG smoke evaluation cases.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES), help="Path to JSON evaluation cases.")
    parser.add_argument("--deep-search", action="store_true", help="Use deep search prompts.")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of cases.")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]

    results = []
    for case in cases:
        result = await _run_case(case, args.deep_search)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['id']}: {json.dumps(result, sort_keys=True)}")

    failures = [result for result in results if not result["passed"]]
    print(json.dumps({"total": len(results), "failures": len(failures)}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
