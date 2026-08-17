"""
Adapter for routing Empirico knowledge answers through the standalone model
service.

"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from healthnavi.core.constants import (
    BOLDING_RULES,
    DEEP_SEARCH_MAX_OUTPUT_TOKENS,
    DEEP_SEARCH_PROMPT,
    EXAM_HANDLING,
    GLOBAL_CONDUCT_RULES,
    PHARMACOLOGY_RULES,
    PREEMPTIVE_REASONING_RULES,
    QUERY_CLASSIFICATION_RULES,
    QUICK_SEARCH_MAX_OUTPUT_TOKENS,
    QUICK_SEARCH_PROMPT,
    ROLE_INSTRUCTIONS,
    SECURITY_AND_EVIDENCE_RULES,
)
from healthnavi.evidence_retrieval.services.evidence_search_service import (
    EvidenceSearchService,
)
from healthnavi.evidence_retrieval.config import get_settings
from healthnavi.evidence_retrieval.services.evidence_policy import (
    evidence_policy_sort_key,
)

logger = logging.getLogger(__name__)
DEFAULT_MODEL_SERVICE_BASE_URL = "https://empirico-model-service-e2dgjxq3uq-ew.a.run.app"
USER_SAFE_GENERATION_ERROR = "I couldn't complete this answer right now. Please try again."
WEB_EVIDENCE_SOURCES = {
    "crawl4ai",
    "official_health_api",
    "pubmed",
    "europe_pmc",
    "semantic_scholar",
}
CRAWL_ONLY_ALLOWED_SOURCES = {"crawl4ai", "official_health_api"}
CRAWL_ONLY_MODES = {"crawl", "crawled", "crawler", "web_crawl", "crawl_only"}
SOURCE_PRIORITY = {
    "crawl4ai": 0,
    "pubmed": 1,
    "europe_pmc": 2,
    "semantic_scholar": 3,
    "official_health_api": 4,
}
DEFAULT_SOURCE_PREFERENCE_HINTS = ""
DEFAULT_SOURCE_PREFERENCE_TERMS: tuple[str, ...] = ()
QUERY_TERM_STOPWORDS = {
    "a",
    "about",
    "according",
    "an",
    "and",
    "are",
    "adult",
    "adults",
    "after",
    "before",
    "best",
    "can",
    "care",
    "clinical",
    "current",
    "do",
    "does",
    "evidence",
    "first",
    "for",
    "from",
    "guidance",
    "guideline",
    "guidelines",
    "has",
    "have",
    "how",
    "initial",
    "line",
    "manage",
    "management",
    "medication",
    "medicine",
    "female",
    "male",
    "old",
    "patient",
    "patients",
    "preferred",
    "recommend",
    "recommendation",
    "recommendations",
    "recommended",
    "should",
    "the",
    "standard",
    "therapy",
    "treat",
    "treated",
    "treating",
    "treatment",
    "use",
    "used",
    "using",
    "what",
    "when",
    "which",
    "who",
    "with",
    "without",
    "year",
}
SNIPPET_FOCUS_KEEP_TERMS = {
    "first",
    "initial",
    "line",
    "manage",
    "management",
    "medication",
    "medicine",
    "preferred",
    "recommend",
    "recommendation",
    "recommendations",
    "recommended",
    "regimen",
    "standard",
    "therapy",
    "treat",
    "treated",
    "treating",
    "treatment",
}
SNIPPET_ANSWER_SIGNAL_PATTERNS = (
    r"\b(?:recommend|recommends|recommended|recommendation|recommendations)\b",
    r"\b(?:preferred|first[-\s]?line|standard|initial)\b",
    r"\b(?:backbone|component|components|option|options)\b",
    r"\b(?:regimen|regimens|therapy|therapies|medicine|medicines|drug|drugs)\b",
    r"\b(?:dose|doses|dosing|mg|mcg|gram|grams|daily|weekly|monthly)\b",
    r"\b(?:include|includes|including|composed of|consists of|combination)\b",
    r"\b(?:contraindicated|contraindication|contraindications|avoid|caution)\b",
)
SNIPPET_METADATA_PATTERNS = (
    r"\b(?:number of pages|reference numbers?|copyright|download|skip to main content)\b",
    r"\b(?:isbn|issn|license|creative commons|all rights reserved)\b",
)
SNIPPET_NON_INITIAL_PATTERNS = (
    r"\b(?:second[-\s]?line|subsequent|salvage|rescue|switch|switching)\b",
    r"\b(?:simplification|clinically stable|stable on|long[-\s]?acting)\b",
)
TRUSTED_CRAWL_METADATA_DOMAINS = (
    "afro.who.int",
    "differentiatedservicedelivery.org",
    "health.go.ug",
    "iris.who.int",
    "library.health.go.ug",
    "platform.who.int",
)
SOURCE_LABELS = {
    "crawl4ai": "Crawled Source",
    "official_health_api": "Official Health API",
    "pubmed": "PubMed",
    "europe_pmc": "Europe PMC",
    "semantic_scholar": "Semantic Scholar",
}


async def generate_model_service_response(
    query: str,
    chat_history: str,
    patient_data: str,
    deep_search: bool = False,
    user_role_from_db: Optional[str] = None,
) -> tuple[str, bool, str, list[str]]:
    answer_top_k = _answer_top_k(deep_search)
    prompt_type = "empirico_deep_search" if deep_search else "empirico_quick_search"
    country_code = _evidence_country_code_for_search()
    search_top_k = _evidence_search_top_k(deep_search)
    retrieval_queries = await _retrieval_queries_for_request(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        deep_search=deep_search,
    )
    configured_source_preference_terms = _source_preference_terms()
    source_preference_context = " ".join((query, *retrieval_queries))
    source_preference_terms = _active_source_preference_terms(
        source_preference_context,
        configured_source_preference_terms,
    )
    source_preference_hints = (
        _source_preference_hints() if source_preference_terms else ""
    )

    evidence_search_result = await _search_retrieval_queries(
        queries=retrieval_queries,
        top_k=search_top_k,
        country_code=country_code,
        deep_search=deep_search,
    )
    provider_errors = list(evidence_search_result.get("provider_errors") or [])
    evidence_timings = dict(evidence_search_result.get("timings_ms") or {})
    raw_evidence = list(evidence_search_result.get("items") or [])
    evidence = _filter_evidence_items(
        raw_evidence,
        query=query,
        source_preference_terms=source_preference_terms,
    )[:answer_top_k]
    if not evidence:
        evidence = _filter_evidence_items(
            raw_evidence,
            query=query,
            source_preference_terms=source_preference_terms,
            allow_seed_metadata=True,
        )[: min(3, answer_top_k)]
    evidence = _include_global_evidence_when_helpful(
        query=query,
        evidence=evidence,
        raw_evidence=raw_evidence,
        source_preference_terms=source_preference_terms,
        answer_top_k=answer_top_k,
    )
    evidence = _include_preferred_crawl_source(
        query=query,
        evidence=evidence,
        raw_evidence=raw_evidence,
        source_preference_terms=source_preference_terms,
        answer_top_k=answer_top_k,
    )
    evidence = await _select_answer_evidence(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        evidence=_semantic_selection_pool(
            evidence=evidence,
            raw_evidence=raw_evidence,
            query=query,
            source_preference_terms=source_preference_terms,
            deep_search=deep_search,
        ),
        deep_search=deep_search,
        answer_top_k=answer_top_k,
    )
    evidence = evidence[:answer_top_k]
    citations = _citations_from_evidence(evidence)

    if not citations:
        logger.warning(
            "No web/crawl evidence survived filtering: country_code=%s raw_items=%d provider_errors=%s",
            country_code or "global",
            len(raw_evidence),
            provider_errors,
        )
        return (
            "I couldn't retrieve enough reliable evidence to answer this right now. Please try again.",
            True,
            prompt_type,
            [],
        )

    prompt = _build_live_evidence_prompt(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        deep_search=deep_search,
        user_role_from_db=user_role_from_db,
        country_code=country_code,
        source_preference_hints=source_preference_hints,
        source_list=_source_list_for_prompt(citations),
        evidence_context=_evidence_context_for_prompt(
            evidence,
            deep_search=deep_search,
            query=query,
        ),
    )
    payload = {
        "prompt": prompt,
        "prompt_type": prompt_type,
        "temperature": 0.0,
        "max_output_tokens": (
            _max_output_tokens_for_mode(deep_search)
        ),
        "top_p": 0.9,
        "top_k": 20,
        "candidate_count": 1,
        "require_evidence": False,
    }
    model_name = _model_name_for_mode(deep_search)
    if model_name:
        payload["model"] = model_name

    try:
        data: dict[str, Any] | None = None
        answer = ""
        for attempt in range(2):
            data = await _post_model_response(payload, timeout_seconds=_model_timeout_for_mode(deep_search))
            answer = str(data.get("answer") or "").strip()
            if answer and not _answer_looks_like_service_status(answer):
                break
            if attempt == 0:
                await asyncio.sleep(1.0)
        if data is None:
            data = {}
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Model service returned %s from %s: %s",
            exc.response.status_code,
            exc.request.url,
            _safe_response_text(exc.response),
        )
        return (
            USER_SAFE_GENERATION_ERROR,
            False,
            prompt_type,
            [],
        )
    except httpx.RequestError as exc:
        logger.error("Model service request failed: %s", exc, exc_info=True)
        return (
            USER_SAFE_GENERATION_ERROR,
            False,
            prompt_type,
            [],
        )
    except ValueError as exc:
        logger.error("Model service returned invalid JSON: %s", exc, exc_info=True)
        return (
            USER_SAFE_GENERATION_ERROR,
            False,
            prompt_type,
            [],
        )

    if not answer or _answer_looks_like_service_status(answer):
        return (
            USER_SAFE_GENERATION_ERROR,
            False,
            prompt_type,
            [],
        )
    answer = _sanitize_answer_style(answer)
    answer = await _polish_answer_body_with_model(
        query=query,
        answer=answer,
        deep_search=deep_search,
    )
    answer = _sanitize_answer_style(answer)
    citations = _citations_for_answer(answer, citations, data)
    answer = _ensure_reference_urls(answer, citations)
    followup_questions = await _generate_followup_questions(query, answer, deep_search=deep_search)

    logger.info(
        "Model service response completed: model=%s country_code=%s citations=%d raw_evidence=%d provider_errors=%d timings=%s",
        data.get("model"),
        country_code or "global",
        len(citations),
        len(raw_evidence),
        len(provider_errors),
        {
            "retrieval_queries": retrieval_queries,
            "evidence": evidence_timings,
            "model": data.get("timings_ms") or {},
        },
    )

    return (
        answer,
        bool(data.get("diagnosis_complete", True)),
        str(data.get("prompt_type") or prompt_type),
        followup_questions,
    )


async def _retrieval_queries_for_request(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
) -> tuple[str, ...]:
    fallback = _fallback_retrieval_queries(query, deep_search=deep_search)
    if not fallback:
        return ("clinical medicine",)
    if not _retrieval_planner_enabled(deep_search):
        return fallback

    payload = {
        "prompt": _build_retrieval_query_prompt(
            query=query,
            patient_data=patient_data,
            chat_history=chat_history,
            deep_search=deep_search,
        ),
        "prompt_type": "empirico_retrieval_query_plan",
        "temperature": 0.0,
        "max_output_tokens": 500,
        "top_p": 0.8,
        "top_k": 20,
        "candidate_count": 1,
        "require_evidence": False,
    }
    try:
        data = await _post_model_response(
            payload,
            timeout_seconds=_retrieval_planner_timeout(),
        )
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        logger.warning("Retrieval query planning fell back to the original question: %s", exc)
        return fallback

    planned = _retrieval_queries_from_model_response(data)
    planned_limit = 3 if deep_search else 2
    return _normalized_retrieval_queries([*planned[:planned_limit], *fallback]) or fallback


def _fallback_retrieval_queries(query: str, *, deep_search: bool) -> tuple[str, ...]:
    cleaned = " ".join(query.split())
    if not cleaned:
        return ()
    return _normalized_retrieval_queries([cleaned])


def _build_retrieval_query_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
) -> str:
    max_queries = 4 if deep_search else 3
    return f"""
You create search queries for retrieving medical evidence before answer generation.

Return only valid JSON in this shape:
{{"queries":["query one","query two"]}}

Rules:
- Create 1 to {max_queries} concise web/library search queries.
- Order queries by direct usefulness to the final answer. Query 1 must be the direct-answer query most likely to retrieve the actual clinical option, regimen, dose, threshold, interpretation, or action.
- Preserve clinically relevant context from the user's wording, such as population, setting, jurisdiction, pregnancy, comorbidities, exposure, intervention, comparator, and outcome when present.
- Expand abbreviations or implicit clinical wording only when that would make retrieval clearer.
- If the user includes a city, country, region, or health system, include one query for local/national guidance and one direct clinical-answer query that omits the place when global guidance is likely to contain the regimen, dose, threshold, or standard recommendation.
- When the question asks for clinical action, use complementary queries when possible: one to find authoritative guidance, one to retrieve the direct answer, and one to verify any practical details needed to answer completely.
- When the user asks generally for treatment, management, or regimen and does not mention failure, relapse, refractory disease, previous treatment, second-line, salvage, or rescue therapy, retrieve the current standard initial/first-line approach.
- Do not make the first query only a broad guideline landing-page query when the user needs a practical clinical answer. Put regimen, dose, threshold, adult/child/pregnancy, first-line/initial, or other task terms in query 1 when they are implied by the user question.
- If the answer may involve multiple parts, make sure one query is broad enough to retrieve the full set rather than only the most obvious anchor term.
- Match the verification query to the user's clinical task without inventing likely answer terms.
- Do not create second-line, salvage, rescue, adherence, failure, or advanced-disease queries unless the user asked for those concepts.
- Do not guess the answer's vocabulary. Build semantic query variants that retrieve and verify the answer from external evidence.
- Avoid implementation, adherence, epidemiology, or burden wording unless the user asked for those.
- Prefer wording likely to retrieve current, authoritative medical sources that directly answer the question.
- Do not answer the medical question.
- Do not add source names, country names, conditions, or treatments that are not implied by the user question or context.

User question:
{query}

Context:
{patient_data or "No additional context provided."}

Previous conversation summary:
{chat_history or "No previous conversation."}
""".strip()


def _retrieval_queries_from_model_response(data: dict[str, Any]) -> tuple[str, ...]:
    direct = data.get("queries")
    if isinstance(direct, list):
        return tuple(str(item) for item in direct if isinstance(item, str))

    answer = data.get("answer")
    if isinstance(answer, dict):
        nested = answer.get("queries")
        if isinstance(nested, list):
            return tuple(str(item) for item in nested if isinstance(item, str))
    if isinstance(answer, str):
        parsed = _json_object_from_text(answer)
        if isinstance(parsed, dict):
            nested = parsed.get("queries")
            if isinstance(nested, list):
                return tuple(str(item) for item in nested if isinstance(item, str))
    return ()


def _json_object_from_text(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalized_retrieval_queries(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    queries: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_retrieval_query(value)
        if not cleaned:
            continue
        key = _normalize_search_text(cleaned)
        if key in seen:
            continue
        seen.add(key)
        queries.append(cleaned)
        if len(queries) >= 4:
            break
    return tuple(queries)


def _clean_retrieval_query(value: str) -> str:
    cleaned = " ".join(str(value).replace("\x00", " ").split())
    cleaned = cleaned.strip(" .;:,")
    if len(cleaned) < 3:
        return ""
    return cleaned[:220]


def _retrieval_planner_timeout() -> float:
    return _env_float(
        "EMPIRICO_RETRIEVAL_PLANNER_TIMEOUT_SECONDS",
        5.0,
        minimum=2.0,
        maximum=30.0,
    )


def _retrieval_planner_enabled(deep_search: bool) -> bool:
    key = (
        "EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER"
        if deep_search
        else "EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER"
    )
    raw = os.getenv(key)
    if raw is None:
        raw = os.getenv("EMPIRICO_ENABLE_RETRIEVAL_PLANNER")
    if raw is None:
        return deep_search
    normalized = raw.strip().lower()
    if normalized in {"auto", "adaptive"}:
        return deep_search
    return normalized in {"1", "true", "yes", "on", "enabled"}


async def _search_retrieval_queries(
    *,
    queries: tuple[str, ...],
    top_k: int,
    country_code: Optional[str],
    deep_search: bool,
) -> dict[str, Any]:
    merged_items: list[dict[str, Any]] = []
    provider_errors: list[str] = []
    timings: dict[str, Any] = {}
    semaphore = asyncio.Semaphore(_retrieval_query_concurrency(deep_search))

    async def run_query(index: int, retrieval_query: str) -> tuple[int, str, dict[str, Any]]:
        async with semaphore:
            result = await _search_local_evidence(
                query=retrieval_query,
                top_k=top_k,
                country_code=country_code,
                deep_search=deep_search,
            )
        return index, retrieval_query, result

    query_results = await asyncio.gather(
        *(
            run_query(index, retrieval_query)
            for index, retrieval_query in enumerate(queries, start=1)
        )
    )

    for index, retrieval_query, result in sorted(query_results, key=lambda entry: entry[0]):
        result = dict(result or {})
        provider_errors.extend(list(result.get("provider_errors") or []))
        timings[f"query_{index}"] = {
            "query": retrieval_query,
            "timings_ms": result.get("timings_ms") or {},
        }
        merged_items = _merge_evidence_items(
            merged_items,
            _items_with_retrieval_query(
                list(result.get("items") or []),
                retrieval_query,
            ),
        )
    return {
        "items": merged_items,
        "provider_errors": provider_errors,
        "timings_ms": timings,
    }


def _items_with_retrieval_query(
    items: list[dict[str, Any]],
    retrieval_query: str,
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        raw = dict(copied.get("raw") if isinstance(copied.get("raw"), dict) else {})
        raw.setdefault("query_used", retrieval_query)
        copied["raw"] = raw
        annotated.append(copied)
    return annotated


def _retrieval_query_concurrency(deep_search: bool) -> int:
    key = (
        "EMPIRICO_DEEP_RETRIEVAL_QUERY_CONCURRENCY"
        if deep_search
        else "EMPIRICO_QUICK_RETRIEVAL_QUERY_CONCURRENCY"
    )
    default = 3
    return _env_int(key, default, minimum=1, maximum=4)


def _semantic_selection_pool(
    *,
    evidence: list[dict[str, Any]],
    raw_evidence: list[dict[str, Any]],
    query: str,
    source_preference_terms: tuple[str, ...],
    deep_search: bool,
) -> list[dict[str, Any]]:
    limit = _semantic_selection_candidate_limit(deep_search)
    candidates = _filter_evidence_items(
        raw_evidence,
        query=query,
        source_preference_terms=source_preference_terms,
        allow_seed_metadata=False,
    )
    return _merge_evidence_items(evidence, candidates[:limit])[:limit]


async def _select_answer_evidence(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    evidence: list[dict[str, Any]],
    deep_search: bool,
    answer_top_k: int,
) -> list[dict[str, Any]]:
    candidates = evidence[: _semantic_selection_candidate_limit(deep_search)]
    if not candidates or not _semantic_evidence_selection_enabled(deep_search):
        return candidates[:answer_top_k]
    if len(candidates) == 1:
        return candidates

    payload = {
        "prompt": _build_evidence_selection_prompt(
            query=query,
            patient_data=patient_data,
            chat_history=chat_history,
            evidence=candidates,
            max_sources=answer_top_k,
        ),
        "prompt_type": "empirico_evidence_source_selection",
        "temperature": 0.0,
        "max_output_tokens": 700,
        "top_p": 0.8,
        "top_k": 20,
        "candidate_count": 1,
        "require_evidence": False,
    }
    try:
        data = await _post_model_response(
            payload,
            timeout_seconds=_semantic_selection_timeout(),
        )
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        logger.warning("Evidence source selection fell back to ranked evidence: %s", exc)
        return candidates[:answer_top_k]

    selected_numbers = _evidence_selection_numbers_from_model_response(
        data,
        max_number=len(candidates),
    )
    if not selected_numbers:
        return candidates[:answer_top_k]

    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for number in selected_numbers:
        if number in seen:
            continue
        seen.add(number)
        selected.append(candidates[number - 1])
        if len(selected) >= answer_top_k:
            break
    if selected and len(selected) < answer_top_k:
        selected = _merge_evidence_items(selected, candidates)[:answer_top_k]
    return selected or candidates[:answer_top_k]


def _build_evidence_selection_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    evidence: list[dict[str, Any]],
    max_sources: int,
) -> str:
    return f"""
Select the retrieved medical evidence sources that should be passed to the final answer generator.

Return only valid JSON in this shape:
{{"source_numbers":[1,2,3]}}

Rules:
- Select 1 to {max_sources} source numbers.
- Choose sources that directly answer the user's medical question and contain usable clinical facts.
- Prefer current authoritative sources when they directly answer the question; add supporting papers, prescribing sources, or data sources only when they add clinically useful detail.
- When the question asks for a clinical choice, include candidates that contain the actionable choice and its practical details when such evidence is available.
- Do not choose sources that mainly give background or eligibility context when another candidate directly answers the user's clinical task.
- Preserve jurisdiction-specific sources when the user named a place and the source actually applies to that place.
- Omit sources that are only metadata, bibliographies, acknowledgements, correction notices, tangential background, or statistics unless the user asked for that kind of information.
- Judge relevance from the source title, type, date, URL, retrieval query, and evidence text. Do not answer the medical question.

User question:
{query}

Context:
{patient_data or "No additional context provided."}

Previous conversation summary:
{chat_history or "No previous conversation."}

Retrieved sources:
{_evidence_selection_context(evidence)}
""".strip()


def _evidence_selection_context(evidence: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(evidence, start=1):
        citation = _normalize_evidence_record(item)
        title = str(citation.get("title") if citation else item.get("title") or f"Source {index}")
        source = (
            str(citation.get("source_label") or "")
            if citation
            else SOURCE_LABELS.get(_source_key(item), _source_key(item) or "Source")
        )
        year = citation.get("year") if citation else item.get("year") or _year_from_publication_date(item.get("publication_date"))
        retrieval_query = _evidence_record_retrieval_query(item)
        url = str(citation.get("url") if citation else item.get("url") or item.get("full_text_url") or "")
        snippet_limit = 1200 if _source_key(item) == "crawl4ai" else 700
        snippet = _compact_text(str(item.get("abstract") or item.get("snippet") or ""), snippet_limit)
        parts = [
            f"{index}. {title}",
            f"Type: {item.get('evidence_type') or 'unknown'}",
            f"Source: {source}" if source else "",
            f"Year: {year}" if year else "",
            f"URL: {url}" if url else "",
            f"Retrieval query: {retrieval_query}" if retrieval_query else "",
            f"Evidence: {snippet}" if snippet else _metadata_only_note(item),
        ]
        lines.append("\n".join(part for part in parts if part))
    return "\n\n".join(lines)


def _evidence_selection_numbers_from_model_response(
    data: dict[str, Any],
    *,
    max_number: int,
) -> tuple[int, ...]:
    direct = _first_present(
        data,
        ("source_numbers", "sourceNumbers", "selected_source_numbers", "selectedSourceNumbers", "selected", "sources"),
    )
    numbers = _evidence_selection_numbers_from_unknown(direct, max_number=max_number)
    if numbers:
        return numbers

    answer = data.get("answer")
    if isinstance(answer, dict):
        nested = _first_present(
            answer,
            ("source_numbers", "sourceNumbers", "selected_source_numbers", "selectedSourceNumbers", "selected", "sources"),
        )
        numbers = _evidence_selection_numbers_from_unknown(nested, max_number=max_number)
        if numbers:
            return numbers
    if isinstance(answer, str):
        parsed = _json_object_from_text(answer)
        if isinstance(parsed, dict):
            nested = _first_present(
                parsed,
                ("source_numbers", "sourceNumbers", "selected_source_numbers", "selectedSourceNumbers", "selected", "sources"),
            )
            numbers = _evidence_selection_numbers_from_unknown(nested, max_number=max_number)
            if numbers:
                return numbers
    return ()


def _evidence_selection_numbers_from_unknown(
    value: Any,
    *,
    max_number: int,
) -> tuple[int, ...]:
    raw_numbers: list[int] = []
    if isinstance(value, int):
        raw_numbers.append(value)
    elif isinstance(value, str):
        raw_numbers.extend(int(match) for match in re.findall(r"\b\d+\b", value))
    elif isinstance(value, list):
        for item in value:
            raw_numbers.extend(
                _evidence_selection_numbers_from_unknown(item, max_number=max_number)
            )
    elif isinstance(value, dict):
        nested = _first_present(value, ("number", "source_number", "sourceNumber", "index", "id"))
        raw_numbers.extend(
            _evidence_selection_numbers_from_unknown(nested, max_number=max_number)
        )

    numbers: list[int] = []
    for number in raw_numbers:
        if 1 <= number <= max_number and number not in numbers:
            numbers.append(number)
    return tuple(numbers)


def _semantic_evidence_selection_enabled(deep_search: bool) -> bool:
    key = (
        "EMPIRICO_DEEP_ENABLE_SEMANTIC_EVIDENCE_SELECTION"
        if deep_search
        else "EMPIRICO_QUICK_ENABLE_SEMANTIC_EVIDENCE_SELECTION"
    )
    raw = os.getenv(key)
    if raw is None:
        raw = os.getenv("EMPIRICO_ENABLE_SEMANTIC_EVIDENCE_SELECTION")
    if raw is None:
        return False
    raw = raw.strip().lower()
    return raw not in {"0", "false", "off", "no", "none", "disabled"}


def _semantic_selection_timeout() -> float:
    return _env_float(
        "EMPIRICO_EVIDENCE_SELECTION_TIMEOUT_SECONDS",
        8.0,
        minimum=2.0,
        maximum=90.0,
    )


def _semantic_selection_candidate_limit(deep_search: bool) -> int:
    default = 24 if deep_search else 18
    return _env_int(
        "EMPIRICO_EVIDENCE_SELECTION_CANDIDATE_LIMIT",
        default,
        minimum=2,
        maximum=30,
    )


def _build_live_evidence_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
    user_role_from_db: Optional[str],
    country_code: Optional[str],
    source_preference_hints: str,
    source_list: str,
    evidence_context: str,
) -> str:
    prompt_template = DEEP_SEARCH_PROMPT if deep_search else QUICK_SEARCH_PROMPT
    prompt = prompt_template.format(
        sources=source_list,
        context=evidence_context,
        role_instruction=_role_instruction(user_role_from_db),
        bolding_rules=BOLDING_RULES,
        exam_handling=EXAM_HANDLING,
        global_conduct_rules=_live_global_conduct_rules(),
        query_classification_rules=QUERY_CLASSIFICATION_RULES,
        preemptive_reasoning_rules=PREEMPTIVE_REASONING_RULES,
        pharmacology_rules=PHARMACOLOGY_RULES,
        references_rules=_live_references_rules(),
        security_and_evidence_rules=SECURITY_AND_EVIDENCE_RULES,
    )
    user_context_block = f"""
### USER QUESTION:
{query}

### CONTEXT (if provided):
{patient_data or "No additional context provided."}

### PREVIOUS CONVERSATION SUMMARY:
{chat_history or "No previous conversation."}

### LOCAL EVIDENCE SOURCE SELECTION:
The evidence source-selection hint is {country_code or "not set"}.
This is only a retrieval preference. Do not treat it as a user location unless the user explicitly says so.

### SOURCE PREFERENCE:
Prefer retrieved sources matching these source hints when they are relevant: {source_preference_hints or "none"}.
If the user explicitly asks for a different jurisdiction, source, or setting, follow the user's query and the retrieved evidence.

### CITATION CONTROL:
- Use only the numbered sources listed in AVAILABLE SOURCES / EVIDENCE BASE.
- Do not cite [1], [2], or any other marker unless that exact source number is present in the evidence block.
- Do not use static cached-library references unless they appear in the evidence block.
- Inline citation markers must be clickable markdown links using the source URL, for example [1](https://example.org/source).
- When a primary source page and a secondary article both support a recommendation, cite the primary source page first.
- If a source note says full document text was not extracted, use it only as a retrieved trusted source link and avoid attributing granular document claims to it.
- Do not discuss the sources in the answer body. State the answer directly and use inline citation markers for support.
- Keep the answer inside the user's requested scope. For a direct clinical-choice question, give the practical choice, brief rationale, and the modifiers that alter that choice; leave out unrelated care-pathway details.
- In quick search, ordinary direct questions should be answered in 1-2 short paragraphs plus References. Do not add extra headings, bullets, targets, monitoring, follow-up, epidemiology, or implementation details unless the user asked or they change the answer.
- For medication or regimen questions, do not answer with only a broad label such as "standard regimen", "6-month regimen", "combination therapy", or "first-line therapy" when any retrieved evidence sentence names the actual components, dose, or duration. Put those practical details in the first paragraph.
- Respect population qualifiers exactly. If the user asks about adults, do not add infant, child, neonate, pregnancy, or breastfeeding recommendations unless the user asked or they alter the adult answer.
- Distinguish treatment from prevention, prophylaxis, screening, and monitoring. If the user asks how a condition is treated, do not answer with prevention/prophylaxis alone.
- If a source title or evidence block covers a broader scope than the user asked about, extract only the part needed for the user's question and do not repeat the broader-scope wording.
"""
    return f"{prompt}\n\n{user_context_block.strip()}"


def _live_global_conduct_rules() -> str:
    return GLOBAL_CONDUCT_RULES


def _live_references_rules() -> str:
    return """
### REFERENCES ###
End with:
**References**

Rules:
- List only sources actually used and grounded in the EVIDENCE BASE / AVAILABLE SOURCES.
- Use a numbered list matching inline citation numbers.
- Use clickable markdown inline citations in the answer body, for example [1](URL). If two sources support the same claim, use separate links such as [1](URL) [2](URL).
- Include the exact full source URL text.
- Format: 1. Source title - source/publisher, year - full URL
- If source/publisher or year is unavailable, omit that missing metadata instead of writing placeholders such as n.d.
- Do not invent page numbers, publications, URLs, PMIDs, PMCIDs, DOIs, or source titles.
- If multiple editions of the same source series appear in the evidence, cite the **most recent** edition that supports the recommendation.
- Prefer the most current authoritative source that directly answers the question. Cite older supporting studies only when they add a clinically relevant point not covered by current guidance.
""".strip()


def _evidence_search_top_k(deep_search: bool) -> int:
    default = 18 if deep_search else 6
    mode_key = "EMPIRICO_DEEP_SEARCH_TOP_K" if deep_search else "EMPIRICO_QUICK_SEARCH_TOP_K"
    raw = os.getenv(mode_key) or os.getenv("EMPIRICO_EVIDENCE_SEARCH_TOP_K") or str(default)
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, min(value, 25))


def _answer_top_k(deep_search: bool) -> int:
    default = 10 if deep_search else 6
    key = "EMPIRICO_DEEP_ANSWER_TOP_K" if deep_search else "EMPIRICO_QUICK_ANSWER_TOP_K"
    return _env_int(key, default, minimum=6, maximum=12)


def _model_timeout_for_mode(deep_search: bool) -> float:
    key = "EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS" if deep_search else "EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS"
    minimum_timeout = 60.0 if deep_search else 8.0
    global_timeout = _env_float(
        "MODEL_SERVICE_TIMEOUT_SECONDS",
        120.0,
        minimum=minimum_timeout,
        maximum=300.0,
    )
    raw_mode_timeout = os.getenv(key)
    if raw_mode_timeout is None or not raw_mode_timeout.strip():
        return global_timeout
    try:
        raw_mode_value = float(raw_mode_timeout)
    except ValueError:
        return global_timeout
    if raw_mode_value < minimum_timeout:
        return global_timeout
    mode_timeout = _env_float(key, global_timeout, minimum=minimum_timeout, maximum=300.0)
    return min(mode_timeout, global_timeout)


def _model_name_for_mode(deep_search: bool) -> str | None:
    key = "EMPIRICO_DEEP_MODEL_NAME" if deep_search else "EMPIRICO_QUICK_MODEL_NAME"
    raw = (os.getenv(key) or os.getenv("EMPIRICO_MODEL_NAME") or "").strip()
    if raw.lower() in {"", "none", "null", "default", "auto"}:
        return None
    return raw


def _max_output_tokens_for_mode(deep_search: bool) -> int:
    if deep_search:
        return _env_int(
            "EMPIRICO_DEEP_MAX_OUTPUT_TOKENS",
            min(DEEP_SEARCH_MAX_OUTPUT_TOKENS, 3600),
            minimum=500,
            maximum=DEEP_SEARCH_MAX_OUTPUT_TOKENS,
        )
    return _env_int(
        "EMPIRICO_QUICK_MAX_OUTPUT_TOKENS",
        min(QUICK_SEARCH_MAX_OUTPUT_TOKENS, 900),
        minimum=300,
        maximum=QUICK_SEARCH_MAX_OUTPUT_TOKENS,
    )


def _search_settings_for_mode(deep_search: bool):
    settings = get_settings()
    prefix = "EMPIRICO_DEEP" if deep_search else "EMPIRICO_QUICK"
    retrieval_default = settings.retrieval_time_budget_seconds if deep_search else min(settings.retrieval_time_budget_seconds, 10.0)
    crawl_default = settings.crawl_time_budget_seconds if deep_search else min(settings.crawl_time_budget_seconds, 8.0)
    request_timeout_default = settings.request_timeout_seconds if deep_search else min(settings.request_timeout_seconds, 12)
    crawl_sources_default = settings.crawl_max_sources if deep_search else min(settings.crawl_max_sources, 6)
    crawl_pages_default = settings.crawl_max_pages if deep_search else min(settings.crawl_max_pages, 8)
    max_results_default = settings.max_results_per_provider if deep_search else min(settings.max_results_per_provider, 6)
    updates = {
        "retrieval_time_budget_seconds": _env_float_override(
            f"{prefix}_RETRIEVAL_TIME_BUDGET_SECONDS",
            retrieval_default,
            minimum=1.0,
            maximum=60.0,
            reject_below=8.0,
        ),
        "crawl_time_budget_seconds": _env_float_override(
            f"{prefix}_CRAWL_TIME_BUDGET_SECONDS",
            crawl_default,
            minimum=0.5,
            maximum=60.0,
            reject_below=8.0,
        ),
        "request_timeout_seconds": _env_int_override(
            f"{prefix}_REQUEST_TIMEOUT_SECONDS",
            request_timeout_default,
            minimum=1,
            maximum=60,
            reject_below=10,
        ),
        "crawl_max_sources": _env_int_override(
            f"{prefix}_CRAWL_MAX_SOURCES",
            crawl_sources_default,
            minimum=1,
            maximum=12,
            reject_below=6,
        ),
        "crawl_max_pages": _env_int_override(
            f"{prefix}_CRAWL_MAX_PAGES",
            crawl_pages_default,
            minimum=1,
            maximum=25,
            reject_below=8,
        ),
        "max_results_per_provider": _env_int_override(
            f"{prefix}_MAX_RESULTS_PER_PROVIDER",
            max_results_default,
            minimum=1,
            maximum=15,
        ),
    }
    return settings.model_copy(update=updates)


def _env_int(key: str, default: int, *, minimum: int, maximum: int) -> int:
    _ensure_evidence_env_loaded()
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _env_float(key: str, default: float, *, minimum: float, maximum: float) -> float:
    _ensure_evidence_env_loaded()
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _env_int_override(
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
    reject_below: int | None = None,
) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return max(minimum, min(default, maximum))
    try:
        value = int(raw)
    except ValueError:
        return max(minimum, min(default, maximum))
    if reject_below is not None and value < reject_below:
        return max(minimum, min(default, maximum))
    return max(minimum, min(value, maximum))


def _env_float_override(
    key: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
    reject_below: float | None = None,
) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return max(minimum, min(default, maximum))
    try:
        value = float(raw)
    except ValueError:
        return max(minimum, min(default, maximum))
    if reject_below is not None and value < reject_below:
        return max(minimum, min(default, maximum))
    return max(minimum, min(value, maximum))


def _ensure_evidence_env_loaded() -> None:
    try:
        get_settings()
    except Exception:
        logger.debug("Could not eagerly load evidence retrieval env settings", exc_info=True)


def _filter_evidence_items(
    items: list[dict[str, Any]],
    *,
    query: str = "",
    source_preference_terms: tuple[str, ...] = (),
    allow_seed_metadata: bool = False,
) -> list[dict[str, Any]]:
    mode = os.getenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web").strip().lower()
    if mode in {"all", "default_all", "unfiltered"}:
        return sorted(
            items,
            key=lambda item: _source_priority(item, source_preference_terms, query),
        )

    crawl_only = mode in CRAWL_ONLY_MODES
    filtered: list[dict[str, Any]] = []
    statistics_query = _is_statistics_query(query)
    for item in items:
        source = _source_key(item)
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        provider = str(raw.get("provider") or "").strip().lower()
        retrieval_mode = str(raw.get("retrieval_mode") or "").strip().lower()

        if source not in WEB_EVIDENCE_SOURCES:
            continue
        if crawl_only and source not in CRAWL_ONLY_ALLOWED_SOURCES:
            continue
        if source == "crawl4ai" and retrieval_mode == "pdf_seed_metadata":
            if not allow_seed_metadata:
                continue
            if not _is_relevant_trusted_seed_metadata(
                item,
                query=query,
                source_preference_terms=source_preference_terms,
            ):
                continue
        if query and _is_metric_indicator_item(item):
            if not statistics_query:
                continue
            if _item_query_term_coverage(item, query) < 2:
                continue
        if (
            query
            and source == "crawl4ai"
            and not _item_matches_source_preference(item, source_preference_terms)
            and _item_query_term_coverage(item, query) < 1
        ):
            continue
        filtered.append(item)
    return sorted(
        filtered,
        key=lambda item: _source_priority(item, source_preference_terms, query),
    )


def _include_global_evidence_when_helpful(
    *,
    query: str,
    evidence: list[dict[str, Any]],
    raw_evidence: list[dict[str, Any]],
    source_preference_terms: tuple[str, ...],
    answer_top_k: int,
) -> list[dict[str, Any]]:
    if not evidence or not source_preference_terms or answer_top_k <= 1:
        return evidence

    has_global_evidence = any(
        not _item_matches_source_preference(item, source_preference_terms)
        for item in evidence
    )
    if has_global_evidence:
        return evidence

    explicit_preference_query = _query_mentions_source_preference(query, source_preference_terms)
    should_broaden = len(evidence) < min(3, answer_top_k) or not explicit_preference_query
    if not should_broaden:
        return evidence

    global_candidates = [
        item
        for item in _filter_evidence_items(
            raw_evidence,
            query=query,
            source_preference_terms=(),
            allow_seed_metadata=False,
        )
        if not _item_matches_source_preference(item, source_preference_terms)
        and item.get("evidence_type") != "official_indicator"
    ]
    if not global_candidates:
        return evidence

    existing_keys = {_evidence_item_key(item) for item in evidence}
    global_candidate = next(
        (
            item
            for item in global_candidates
            if _evidence_item_key(item) not in existing_keys
        ),
        None,
    )
    if global_candidate is None:
        return evidence

    if len(evidence) < answer_top_k:
        return [*evidence, global_candidate]
    return [*evidence[: answer_top_k - 1], global_candidate]


def _include_preferred_crawl_source(
    *,
    query: str,
    evidence: list[dict[str, Any]],
    raw_evidence: list[dict[str, Any]],
    source_preference_terms: tuple[str, ...],
    answer_top_k: int,
) -> list[dict[str, Any]]:
    if answer_top_k <= 0:
        return evidence
    if any(
        _source_key(item) == "crawl4ai"
        and _item_matches_source_preference(item, source_preference_terms)
        for item in evidence
    ):
        return evidence

    candidates = [
        item
        for item in _filter_evidence_items(
            raw_evidence,
            query=query,
            source_preference_terms=source_preference_terms,
            allow_seed_metadata=False,
        )
        if _source_key(item) == "crawl4ai"
        and _item_matches_source_preference(item, source_preference_terms)
    ]
    if not candidates:
        return evidence

    existing_keys = {_evidence_item_key(item) for item in evidence}
    preferred = next(
        (
            item
            for item in candidates
            if _evidence_item_key(item) not in existing_keys
        ),
        None,
    )
    if preferred is None:
        return evidence

    merged = [preferred, *evidence]
    return merged[:answer_top_k]


def _evidence_item_key(item: dict[str, Any]) -> str:
    return str(
        item.get("id")
        or item.get("url")
        or item.get("full_text_url")
        or item.get("title")
        or repr(item)
    )


def _source_priority(
    item: dict[str, Any],
    source_preference_terms: tuple[str, ...] = (),
    query: str = "",
) -> tuple[int, int, int, int, int, int, int]:
    source = _source_key(item)
    policy_tier, type_tier = evidence_policy_sort_key(
        source=source,
        evidence_type=str(item.get("evidence_type") or ""),
        url=str(item.get("url") or item.get("full_text_url") or ""),
        text=_item_search_text(item),
    )
    direct_title_match = _item_title_url_specificity(item, query)
    return (
        0 if direct_title_match else 1,
        policy_tier,
        0 if _item_matches_source_preference(item, source_preference_terms) else 1,
        type_tier,
        -direct_title_match,
        -_item_answer_specificity(item, query),
        -_item_publication_year(item),
        SOURCE_PRIORITY.get(source, 99),
    )


def _item_publication_year(item: dict[str, Any]) -> int:
    year = _evidence_record_year(item)
    if isinstance(year, int):
        value = year
    else:
        parsed = _year_from_publication_date(year)
        value = int(parsed) if isinstance(parsed, int) else 0
    return value if 1900 <= value <= 2100 else 0


def _item_answer_specificity(item: dict[str, Any], query: str) -> int:
    query_terms = set(_normalized_query_terms(query))
    if not query_terms:
        return 0
    text_terms = set(re.findall(r"[a-z0-9]{4,}", _item_search_text(item)))
    return len(query_terms.intersection(text_terms))


def _item_title_url_specificity(item: dict[str, Any], query: str) -> int:
    query_terms = set(_normalized_query_terms(query))
    if not query_terms:
        return 0
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    text = _normalize_search_text(
        " ".join(
            str(part)
            for part in (
                item.get("title"),
                item.get("url"),
                item.get("full_text_url"),
                raw.get("source_url"),
            )
            if part
        )
    )
    return sum(1 for term in query_terms if term in text)


def _merge_evidence_items(
    primary_items: list[dict[str, Any]],
    fallback_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*primary_items, *fallback_items]:
        key = str(item.get("id") or item.get("url") or item.get("full_text_url") or item.get("title") or "")
        if not key:
            key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _item_matches_source_preference(
    item: dict[str, Any],
    source_preference_terms: tuple[str, ...],
) -> bool:
    if not source_preference_terms:
        return False
    text = _item_search_text(item)
    return any(term in text for term in source_preference_terms)


def _query_mentions_source_preference(
    query: str,
    source_preference_terms: tuple[str, ...],
) -> bool:
    if not query or not source_preference_terms:
        return False
    query_text = _normalize_search_text(query)
    return any(term in query_text for term in source_preference_terms)


def _is_metric_indicator_item(item: dict[str, Any]) -> bool:
    if _source_key(item) != "official_health_api":
        return False
    evidence_type = str(item.get("evidence_type") or "").strip().lower()
    if evidence_type == "official_indicator":
        return True
    text = _item_search_text(item)
    return (
        "indicator:" in text
        or "ghoapi.azureedge.net" in text
        or "api.worldbank.org" in text
    )


def _is_statistics_query(query: str) -> bool:
    text = _normalize_search_text(query)
    return bool(
        re.search(
            r"\b(?:statistic|statistics|data|indicator|coverage|prevalence|"
            r"incidence|rate|rates|burden|trend|trends|mortality|cases|count|"
            r"how many|percentage|percent|proportion)\b",
            text,
        )
    )


def _is_relevant_trusted_seed_metadata(
    item: dict[str, Any],
    *,
    query: str,
    source_preference_terms: tuple[str, ...],
) -> bool:
    text = _item_search_text(item)
    if not any(domain in text for domain in TRUSTED_CRAWL_METADATA_DOMAINS):
        return False
    if source_preference_terms and not any(term in text for term in source_preference_terms):
        return False
    source_preference_tokens = {
        token
        for term in source_preference_terms
        for token in _normalized_query_terms(term)
    }
    query_terms = tuple(
        term
        for term in _normalized_query_terms(query)
        if term not in source_preference_tokens
    )
    return not query_terms or any(term in text for term in query_terms)


def _normalized_query_terms(query: str) -> tuple[str, ...]:
    words = re.findall(r"[a-z0-9]{3,}", query.lower())
    return tuple(
        dict.fromkeys(
            word
            for word in words
            if not word.isdigit() and word not in QUERY_TERM_STOPWORDS
        )
    )


def _snippet_focus_terms(query: str) -> tuple[str, ...]:
    words = re.findall(r"[a-z0-9]{3,}", query.lower())
    terms = list(
        dict.fromkeys(
            word
            for word in words
            if (
                not word.isdigit()
                and (
                    word not in QUERY_TERM_STOPWORDS
                    or word in SNIPPET_FOCUS_KEEP_TERMS
                )
            )
        )
    )
    term_set = set(terms)
    if "initial" in term_set and "firstline" not in term_set:
        terms.append("firstline")
        term_set.add("firstline")
    if (
        "firstline" in term_set
        or {"first", "line"}.issubset(term_set)
    ) and "initial" not in term_set:
        terms.append("initial")
    return tuple(terms)


def _item_query_term_coverage(item: dict[str, Any], query: str) -> int:
    text = _item_search_text(item)
    return sum(1 for term in _normalized_query_terms(query) if term in text)


def _item_search_text(item: dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    parts = [
        item.get("title"),
        item.get("abstract"),
        item.get("snippet"),
        item.get("journal_or_publisher"),
        item.get("url"),
        item.get("full_text_url"),
        raw.get("provider"),
        raw.get("retrieval_mode"),
        raw.get("publisher"),
        raw.get("source"),
        raw.get("source_name"),
        raw.get("source_url"),
        raw.get("domain"),
        raw.get("country"),
        raw.get("country_code"),
        raw.get("country_codes"),
        raw.get("document_title"),
    ]
    return _normalize_search_text(" ".join(str(part) for part in parts if part))


def _normalize_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _citations_from_evidence(items: list[dict[str, Any]]) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for item in items:
        citation = _normalize_evidence_record(item)
        if citation is None:
            continue
        citations.append(citation)
    return _assign_citation_numbers(citations)


def _citations_for_answer(
    answer: str,
    local_citations: list[dict[str, object]],
    model_data: dict[str, Any],
) -> list[dict[str, object]]:
    model_citations = _citations_from_model_response(model_data)
    if not model_citations:
        return _assign_citation_numbers(local_citations)

    used_numbers = _inline_reference_numbers(answer)
    if any(number > len(local_citations) for number in used_numbers):
        return _assign_citation_numbers([*local_citations, *model_citations])
    return _assign_citation_numbers(_merge_citation_records(local_citations, model_citations))


def _citations_from_model_response(model_data: dict[str, Any]) -> list[dict[str, object]]:
    return _normalize_evidence_collection(
        [
            model_data.get("citations"),
            model_data.get("evidence"),
            model_data.get("references"),
            model_data.get("sources"),
        ]
    )


def _normalize_evidence_collection(value: Any) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []

    def visit(item: Any) -> None:
        if isinstance(item, list):
            for entry in item:
                visit(entry)
            return
        if not isinstance(item, dict):
            return

        link = _normalize_evidence_record(item)
        if link is not None:
            links.append(link)

        for key in ("items", "citations", "evidence", "references", "sources", "results", "documents"):
            if key in item:
                visit(item[key])

    visit(value)
    return _merge_citation_records([], links)


def _normalize_evidence_record(record: dict[str, Any]) -> dict[str, object] | None:
    url = _source_url_from_record(record)
    if not url:
        return None

    page = _evidence_record_exact_page(record) or _exact_page_from_url(url)
    page_url = _source_url_with_exact_page(url, page) if page is not None else url
    source_key = _evidence_record_source_key(record)
    source_label = (
        _evidence_record_source_label(record)
        or SOURCE_LABELS.get(source_key, source_key or "Source")
    )
    citation: dict[str, object] = {
        "title": _evidence_record_label(record, page_url, page),
        "source_label": source_label,
        "journal": _text_from_unknown(record.get("journal")) or source_label,
        "year": _evidence_record_year(record),
        "url": page_url,
        "search_text": _evidence_record_search_text(record),
    }
    retrieval_query = _evidence_record_retrieval_query(record)
    if retrieval_query:
        citation["retrieval_query"] = retrieval_query
    doi = _text_from_unknown(record.get("doi"))
    if doi:
        citation["doi"] = doi
    return citation


def _assign_citation_numbers(citations: list[dict[str, object]]) -> list[dict[str, object]]:
    numbered: list[dict[str, object]] = []
    for index, citation in enumerate(citations, start=1):
        next_citation = dict(citation)
        next_citation["number"] = index
        numbered.append(next_citation)
    return numbered


def _merge_citation_records(
    existing: list[dict[str, object]],
    incoming: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    index_by_key: dict[str, int] = {}

    for citation in [*existing, *incoming]:
        normalized = dict(citation)
        keys = [_citation_url_key(normalized), _citation_label_key(normalized)]
        existing_index = next(
            (index_by_key[key] for key in keys if key and key in index_by_key),
            None,
        )
        if existing_index is not None:
            merged[existing_index] = _merge_citation_record(merged[existing_index], normalized)
            continue

        new_index = len(merged)
        merged.append(normalized)
        for key in keys:
            if key:
                index_by_key[key] = new_index

    return merged


def _merge_citation_record(
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(existing)
    if _citation_label_specificity_score(incoming) > _citation_label_specificity_score(existing) + 1:
        merged["title"] = incoming.get("title") or existing.get("title")
    for key in ("source_label", "journal", "year", "url", "doi", "retrieval_query", "search_text"):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]
    return merged


def _citation_url_key(citation: dict[str, object]) -> str:
    return str(citation.get("url") or "").strip().lower()


def _citation_label_key(citation: dict[str, object]) -> str:
    title = _normalize_search_text(str(citation.get("title") or ""))
    return f"label:{title}" if title else ""


def _citation_label_specificity_score(citation: dict[str, object]) -> float:
    title = _compact_plain_text(str(citation.get("title") or ""))
    source = _compact_plain_text(str(citation.get("source_label") or ""))
    structural_detail = len([part for part in re.split(r"[;:]", title) if len(part.strip()) >= 3])
    return min(len(title), 180) / 45 + structural_detail * 1.5 + (1.0 if source else 0.0)


def _source_url_from_record(record: dict[str, Any]) -> str | None:
    direct = _clean_source_url(
        _text_from_unknown(
            _first_present(
                record,
                (
                    "url",
                    "href",
                    "link",
                    "uri",
                    "full_text_url",
                    "fullTextUrl",
                    "reference_url",
                    "referenceUrl",
                    "reference_href",
                    "referenceHref",
                    "signed_url",
                    "signedUrl",
                    "signed_reference_url",
                    "signedReferenceUrl",
                    "source_url",
                    "sourceUrl",
                    "document_url",
                    "documentUrl",
                    "public_source_url",
                    "publicSourceUrl",
                    "source_uri",
                    "sourceUri",
                    "web_url",
                    "webUrl",
                    "canonical_url",
                    "canonicalUrl",
                ),
            )
        )
    )
    if direct:
        return direct

    for key in ("raw", "metadata", "meta", "document", "source", "citation"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_url = _source_url_from_record(nested)
            if nested_url:
                return nested_url
    return None


def _clean_source_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.replace("\\", "/").strip()
    cleaned = re.sub(r"[>)\].,;]+$", "", cleaned).strip()
    if re.match(r"^/v1/references/", cleaned, flags=re.IGNORECASE):
        return f"{_model_service_base_url()}{cleaned}"
    if not re.match(r"^https?://", cleaned, flags=re.IGNORECASE):
        return None
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return None
    hostname = parsed.hostname or ""
    if hostname not in {"localhost", "127.0.0.1", "::1"} and "." not in hostname:
        return None
    return cleaned


def _source_url_with_exact_page(url: str, page: int) -> str:
    if "#page=" in url.lower():
        return url
    return f"{url}#page={page}"


def _exact_page_from_url(url: str) -> int | None:
    match = re.search(r"#page=(\d+)\b", url, flags=re.IGNORECASE)
    if not match:
        return None
    page = int(match.group(1))
    return page if page > 0 else None


def _evidence_record_exact_page(record: dict[str, Any]) -> int | None:
    direct = _number_from_unknown(
        _first_present(record, ("page_start", "pageStart", "pageNumber", "page_number", "page"))
    )
    if direct is not None:
        return direct
    for key in ("raw", "metadata", "meta", "document", "source", "citation"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_page = _evidence_record_exact_page(nested)
            if nested_page is not None:
                return nested_page
    return None


def _evidence_record_source_key(record: dict[str, Any]) -> str:
    source = record.get("source")
    if isinstance(source, dict):
        return _normalize_search_text(
            _text_from_unknown(_first_present(source, ("value", "name", "id", "label"))) or ""
        )
    if isinstance(source, str):
        return _normalize_search_text(source)
    provider = _text_from_unknown(_first_present(record, ("provider", "provider_name", "providerName")))
    if provider:
        return _normalize_search_text(provider)
    return _source_key(record)


def _evidence_record_source_label(record: dict[str, Any]) -> str | None:
    direct = _text_from_unknown(
        _first_present(
            record,
            (
                "source_label",
                "sourceLabel",
                "journal_or_publisher",
                "publisher",
                "journal",
                "venue",
            ),
        )
    )
    if direct:
        return direct
    source = record.get("source")
    if isinstance(source, dict):
        source_label = _text_from_unknown(_first_present(source, ("display", "name", "label", "value")))
        if source_label:
            return source_label
    source_label_fallback = SOURCE_LABELS.get(source, source) if isinstance(source, str) else None
    for key in ("raw", "metadata", "meta", "document", "citation"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_label = _evidence_record_source_label(nested)
            if nested_label:
                return nested_label
    return source_label_fallback


def _evidence_record_title(record: dict[str, Any]) -> str | None:
    direct = _text_from_unknown(
        _first_present(
            record,
            (
                "citation_label",
                "citationLabel",
                "sourceTitle",
                "source_title",
                "documentTitle",
                "document_title",
                "title",
                "label",
                "name",
                "short_citation",
            ),
        )
    )
    if direct:
        return direct
    for key in ("raw", "metadata", "meta", "document", "source", "citation"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_title = _evidence_record_title(nested)
            if nested_title:
                return nested_title
    return None


def _evidence_record_label(record: dict[str, Any], url: str, page: int | None) -> str:
    raw_title = (
        _evidence_record_title(record)
        or _text_from_unknown(_first_present(record, ("label", "source_label", "sourceLabel", "source", "name")))
        or _label_from_url(url)
    )
    title = _clean_reference_label_base(raw_title)
    title_with_page = (
        title
        if page is None or _title_already_has_exact_page(title, page)
        else f"{title}, p. {page}"
    )
    locator = _evidence_record_display_locator(record, title, page)
    heading = _evidence_record_specific_heading(record, title, locator)
    version = _kb_version_label(record)
    return _compact_nullable_text([title_with_page, locator, heading, version]) or "Clinical source"


def _evidence_record_display_locator(
    record: dict[str, Any],
    title: str,
    page: int | None,
) -> str | None:
    locator = _evidence_record_locator(record)
    if not locator:
        return None
    normalized_locator = _normalize_search_text(locator)
    normalized_title = _normalize_search_text(title)
    if normalized_locator == normalized_title or normalized_locator in normalized_title:
        return None
    if re.match(r"^(chunk|document|doc|id)\b", normalized_locator, flags=re.IGNORECASE):
        return None
    if page is not None and re.match(rf"^(p(?:age)?\.?\s*)?{page}$", normalized_locator, flags=re.IGNORECASE):
        return None
    if re.match(r"^[a-z0-9_-]+:\d{3,}:[a-z0-9_-]+$", normalized_locator, flags=re.IGNORECASE):
        return None
    return locator


def _evidence_record_locator(record: dict[str, Any]) -> str | None:
    direct = _text_from_unknown(
        _first_present(
            record,
            (
                "section_title",
                "sectionTitle",
                "heading",
                "chapter",
                "topic",
                "condition",
                "locator",
                "loc",
                "page_label",
                "pageLabel",
                "section",
                "page",
                "chunk_id",
                "chunkId",
                "document_id",
                "documentId",
            ),
        )
    )
    if direct:
        return direct
    for key in ("metadata", "meta", "document", "source", "citation", "raw"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_locator = _evidence_record_locator(nested)
            if nested_locator:
                return nested_locator
    return None


def _evidence_record_specific_heading(
    record: dict[str, Any],
    title: str,
    locator: str | None,
) -> str | None:
    existing = _normalize_search_text(" ".join(part for part in (title, locator or "") if part))
    headings: list[str] = []
    for candidate in _evidence_record_heading_candidates(record):
        heading = _clean_evidence_heading(candidate)
        if not heading:
            continue
        normalized = _normalize_search_text(heading)
        if not normalized or normalized in existing:
            continue
        if any(_normalize_search_text(item) == normalized for item in headings):
            continue
        headings.append(heading)
        if len(headings) >= 2:
            break
    return "; ".join(headings) if headings else None


def _evidence_record_heading_candidates(record: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    direct = _text_from_unknown(
        _first_present(record, ("subsection_title", "subsectionTitle", "heading", "topic", "condition"))
    )
    _append_evidence_heading_candidate(candidates, direct)

    for key in ("metadata", "meta", "raw", "document", "source", "citation"):
        nested = record.get(key)
        if not isinstance(nested, dict):
            continue
        nested_heading = _text_from_unknown(
            _first_present(
                nested,
                (
                    "subsection_title",
                    "subsectionTitle",
                    "heading",
                    "topic",
                    "condition",
                    "section_path",
                    "sectionPath",
                ),
            )
        )
        _append_evidence_heading_candidate(candidates, nested_heading)

    for text in _evidence_record_body_text_candidates(record):
        candidates.extend(_markdown_headings_from_text(text))
        candidates.extend(_lead_label_candidates_from_evidence_text(text))
    return candidates


def _append_evidence_heading_candidate(candidates: list[str], heading: str | None) -> None:
    if not heading:
        return
    candidates.append(heading)
    candidates.extend(_evidence_record_path_heading_candidates(heading))


def _evidence_record_path_heading_candidates(value: str) -> list[str]:
    parts = [
        part.strip()
        for part in re.split(r"\s*(?:>|>>|\||;)\s*", value)
        if part.strip()
    ]
    return list(reversed(parts)) if len(parts) > 1 else []


def _evidence_record_body_text_candidates(record: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen_records: set[int] = set()
    seen_texts: set[str] = set()

    def add(value: Any) -> None:
        text = _text_from_unknown(value)
        if not text:
            return
        normalized = _normalize_search_text(text)
        if not normalized or normalized in seen_texts:
            return
        seen_texts.add(normalized)
        candidates.append(text)

    def visit(source: dict[str, Any]) -> None:
        record_id = id(source)
        if record_id in seen_records:
            return
        seen_records.add(record_id)
        for key in (
            "snippet",
            "text",
            "content",
            "abstract",
            "body",
            "body_text",
            "bodyText",
            "page_text",
            "pageText",
            "chunk_text",
            "chunkText",
            "markdown",
        ):
            add(source.get(key))
        for key in ("metadata", "meta", "raw", "document", "source", "citation"):
            nested = source.get(key)
            if isinstance(nested, dict):
                visit(nested)

    visit(record)
    return candidates


def _markdown_headings_from_text(text: str) -> list[str]:
    headings: list[str] = []
    seen: set[str] = set()
    line_text = text.replace("\r\n", "\n").replace("\r", "\n")
    for match in re.finditer(r"(?:^|\n)\s{0,3}#{1,6}\s+(.{2,220}?)(?=\s+#{1,6}\s+|\n|$)", line_text):
        heading = match.group(1).strip()
        normalized = _normalize_search_text(heading)
        if normalized and normalized not in seen:
            seen.add(normalized)
            headings.append(heading)
        if len(headings) >= 4:
            break
    return headings


def _lead_label_candidates_from_evidence_text(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    normalized = _compact_plain_text(re.sub(r"#{1,6}\s+", " ", text))
    for segment in re.split(r"\s*(?:[*]|\s+-\s+)\s*", normalized):
        match = re.match(r"^([^:.;!?]{6,90}):", segment.strip())
        candidate = match.group(1).strip() if match else ""
        if not candidate:
            continue
        word_count = len([part for part in candidate.split() if part])
        if word_count < 2 or word_count > 10:
            continue
        key = _normalize_search_text(candidate)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        if len(candidates) >= 3:
            break
    return candidates


def _clean_evidence_heading(value: str) -> str | None:
    cleaned = re.sub(r"^#+\s*", "", value)
    cleaned = re.sub(r"\s+\*.*$", "", cleaned)
    cleaned = re.sub(
        r"\s+(Description|Definition|Signs and Symptoms|Signs|Symptoms|Investigations?|Treatment|Management|Risk factors?|Causes|Classification|Table)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^A-Za-z0-9 .,/()+-]+", " ", cleaned)
    cleaned = _compact_plain_text(_trim_repeated_heading_lead(cleaned))
    if len(cleaned) < 3 or len(cleaned) > 90:
        return None
    if len([part for part in cleaned.split() if part]) > 12:
        return None
    return cleaned


def _trim_repeated_heading_lead(value: str) -> str:
    trimmed = value.strip()
    match = re.match(r"^((?:\d+(?:\.\d+)*\.?\s+)?)([A-Za-z][A-Za-z/-]+)\s+\2\b", trimmed, flags=re.IGNORECASE)
    if not match:
        return trimmed
    return f"{match.group(1)}{match.group(2)}".strip()


def _clean_reference_label_base(value: str) -> str:
    return re.sub(
        r",?\s*(#\s*)?(p|pp|pages?)\.?\s*\d+(\s*[-\u2013]\s*\d+)?\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip().rstrip(",")


def _title_already_has_exact_page(title: str, page: int) -> bool:
    return bool(re.search(rf"(^|\b)(p|page)\.?\s*{page}(\b|$)", title, flags=re.IGNORECASE))


def _kb_version_label(record: dict[str, Any]) -> str | None:
    version = _text_from_unknown(_first_present(record, ("kbVersion", "kb_version", "version")))
    return f"KB {version}" if version else None


def _label_from_url(url: str) -> str:
    try:
        return (urlparse(url).hostname or "Clinical source").removeprefix("www.")
    except ValueError:
        return "Clinical source"


def _evidence_record_retrieval_query(record: dict[str, Any]) -> str | None:
    direct = _text_from_unknown(
        _first_present(record, ("query_used", "queryUsed", "query", "normalized_query", "normalizedQuery"))
    )
    if direct:
        return direct
    for key in ("raw", "metadata", "meta"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_query = _evidence_record_retrieval_query(nested)
            if nested_query:
                return nested_query
    return None


def _evidence_record_search_text(record: dict[str, Any]) -> str:
    nested_metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    nested_raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    nested_source = record.get("source") if isinstance(record.get("source"), dict) else {}
    nested_document = record.get("document") if isinstance(record.get("document"), dict) else {}
    parts: list[Any] = [
        record.get("citation_label"),
        record.get("citationLabel"),
        _evidence_record_title(record),
        _evidence_record_source_label(record),
        _evidence_record_locator(record),
        _source_url_from_record(record),
        record.get("country"),
        record.get("country_code"),
        record.get("jurisdiction"),
        record.get("publisher"),
        record.get("journal_or_publisher"),
        record.get("snippet"),
        record.get("abstract"),
        record.get("text"),
        record.get("content"),
        record.get("heading"),
        record.get("section"),
        record.get("section_title"),
        record.get("chapter"),
        record.get("topic"),
        record.get("condition"),
        record.get("keywords"),
    ]
    for nested in (nested_raw, nested_metadata, nested_source, nested_document):
        parts.extend(
            (
                nested.get("country"),
                nested.get("country_code"),
                nested.get("title"),
                nested.get("source"),
                nested.get("citation_label"),
                nested.get("citationLabel"),
                nested.get("publisher"),
                nested.get("doc_key"),
                nested.get("document_title"),
                nested.get("heading"),
                nested.get("section"),
                nested.get("section_title"),
                nested.get("chapter"),
                nested.get("topic"),
                nested.get("condition"),
                nested.get("keywords"),
                nested.get("guideline_type"),
                nested.get("version_label"),
                nested.get("publication_year"),
                nested.get("public_source_url"),
            )
        )
        parts.append(_source_url_from_record(nested))
    return _compact_plain_text(
        " ".join(text for text in (_text_from_unknown(part) for part in parts) if text)
    )


def _evidence_record_year(record: dict[str, Any]) -> object:
    direct = _number_from_unknown(
        _first_present(record, ("year", "publication_year", "publicationYear"))
    )
    if direct is not None:
        return direct
    date_value = _text_from_unknown(
        _first_present(record, ("publication_date", "publicationDate", "date", "published_at", "publishedAt"))
    )
    year = _year_from_publication_date(date_value)
    if year is not None:
        return year
    for key in ("raw", "metadata", "meta", "document", "source", "citation"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_year = _evidence_record_year(nested)
            if nested_year:
                return nested_year
    return None


def _first_present(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _text_from_unknown(value: Any) -> str | None:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return _compact_nullable_text([_text_from_unknown(item) for item in value])
    if isinstance(value, dict):
        return _compact_nullable_text(
            [
                _text_from_unknown(value.get(key))
                for key in (
                    "text",
                    "display",
                    "drugDisplay",
                    "drug",
                    "name",
                    "label",
                    "code",
                    "drugCode",
                    "sig",
                    "status",
                    "items",
                )
            ]
        )
    if not isinstance(value, str):
        return None
    text = _compact_plain_text(value)
    return text or None


def _number_from_unknown(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if not isinstance(value, str):
        return None
    match = re.search(r"(^|\b)(p|pp|page|pages)?\.?\s*(\d+)(\b|$)", value.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    page = int(match.group(3))
    return page if page > 0 else None


def _compact_nullable_text(parts: list[str | None]) -> str | None:
    text = _compact_plain_text(" ".join(part for part in parts if part))
    return text or None


def _compact_plain_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _inline_reference_numbers(text: str) -> list[int]:
    numbers: list[int] = []
    normalized = re.sub(r"\[\[(\d+(?:\s*,\s*\d+)*)\]\]", r"[\1]", text)
    for match in re.finditer(r"(?<!\[)\[(\d+(?:\s*,\s*\d+)*)\](?:\([^)]*\))?", normalized):
        for raw_number in match.group(1).split(","):
            value = raw_number.strip()
            if value.isdigit():
                numbers.append(int(value))
    return numbers


def _source_list_for_prompt(citations: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for citation in citations:
        number = citation.get("number")
        title = str(citation.get("title") or f"Source {number}")
        url = str(citation.get("url") or "")
        metadata = _citation_metadata_for_prompt(citation)
        if metadata and url:
            lines.append(f"[{number}] {title} - {metadata} - {url}")
        elif url:
            lines.append(f"[{number}] {title} - {url}")
        else:
            lines.append(f"[{number}] {title}")
    return "\n".join(lines)


def _evidence_context_for_prompt(
    items: list[dict[str, Any]],
    *,
    deep_search: bool = False,
    query: str = "",
) -> str:
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        citation = _normalize_evidence_record(item)
        source = (
            str(citation.get("source_label") or "")
            if citation
            else SOURCE_LABELS.get(_source_key(item), _source_key(item) or "Source")
        )
        title = str(citation.get("title") if citation else item.get("title") or f"Source {index}")
        year = citation.get("year") if citation else item.get("year") or _year_from_publication_date(item.get("publication_date"))
        url = str(citation.get("url") if citation else item.get("url") or item.get("full_text_url") or "")
        if deep_search:
            snippet_limit = 1800 if _source_key(item) == "crawl4ai" else 1100
        else:
            snippet_limit = 1800 if _source_key(item) == "crawl4ai" else 800
        retrieval_query = _evidence_record_retrieval_query(item)
        focus_query = " ".join(
            part
            for part in (query, retrieval_query)
            if part
        )
        raw_snippet = str(item.get("abstract") or item.get("snippet") or "")
        snippet = (
            _compact_text(raw_snippet, snippet_limit)
            if deep_search
            else _query_focused_snippet(raw_snippet, focus_query, snippet_limit)
        )
        source_parts = [
            f"Source: {source}" if source else "",
            f"Year: {year}" if year else "",
            f"URL: {url}" if url else "",
        ]
        lines.append(
            "\n".join(
                part
                for part in (
                    f"[{index}] {title}",
                    "; ".join(part for part in source_parts if part),
                    f"Retrieval query: {retrieval_query}" if retrieval_query else "",
                    f"Evidence: {snippet}" if snippet else _metadata_only_note(item),
                )
                if part
            )
        )
    return "\n\n".join(lines)


def _citation_metadata_for_prompt(citation: dict[str, object]) -> str:
    source = str(citation.get("source_label") or "").strip()
    year = citation.get("year")
    parts = [source] if source else []
    if year:
        parts.append(str(year))
    return ", ".join(parts)


def _sanitize_answer_style(answer: str) -> str:
    cleaned = answer.strip()
    cleaned = re.sub(r"\bnotdetailed\b", "not detailed", cleaned, flags=re.IGNORECASE)
    cleaned = _remove_source_attribution_phrasing(cleaned)
    cleaned = re.sub(
        r"\b[Bb]ased on (?:the )?(?:provided|available|retrieved|current|cited)\s+"
        r"(?:evidence|sources?|references?|text|information|source material),?\s*",
        "",
        cleaned,
    )
    source_subject = (
        r"(?:(?:the\s+)?(?:provided|available|retrieved|current|cited)\s+"
        r"(?:evidence|sources?|references?|text|information|source material)"
        r"|(?:the\s+)?(?:evidence|sources?|source material))"
    )
    before_removing_empty_disclaimers = cleaned
    cleaned = re.sub(
        r"(?:^|\n)\s*\*\*Important\s+Caveats?\*\*\s*(?:\n|$)",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:^|(?<=[.!?])\s+)(?:while\s+[^.!?]{0,160},\s*)?"
        r"(?:a\s+)?note\s+of\s+caution\s+is\s+(?:mentioned|noted|included)\b"
        r"[^.!?]*(?:[.!?]|$)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b([A-Z][A-Za-z0-9+ ()/-]{1,80})\s+for\s+all\s+people\s+with\s+"
        r"([^,.\n]+),\s+starting\s+is\s+recommended\s+",
        r"\1 is recommended for all people with \2 and should be started ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b([^.!?\n]{1,140}?),\s+starting\s+is\s+recommended\s+",
        r"\1 and should be started ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"(?:^|(?<=[.!?])\s+){source_subject}\s+(?:does|do)\s+not\s+"
        r"(?:specify|identify|state|name|detail|provide|include)\b[^.!?]*(?:[.!?]|$)\s*",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"(?:^|(?<=[.!?])\s+)(?:there\s+is\s+)?(?:no|insufficient)\s+{source_subject}"
        r"\b[^.!?]*(?:[.!?]|$)\s*",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not cleaned.strip():
        cleaned = before_removing_empty_disclaimers
    cleaned = re.sub(
        rf"\b{source_subject}\s+"
        r"(?:indicates?|shows?|states?|reports?|suggests?|supports?|notes?|says?|discusses?)"
        r"(?:\s+that)?\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(^\s*|(?<=[.!?])\s+)(?:it|they)\s+"
        r"(?:indicates?|shows?|states?|reports?|suggests?|supports?|notes?|says?)"
        r"(?:\s+that)?\s+",
        r"\1",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:within|in)\s+the\s+(?:provided|available|retrieved|current|cited)\s+"
        r"(?:evidence|sources?|references?|text|information|source material)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:the\s+)?source\s+material\s+material\b",
        "evidence",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:^|(?<=[.!?])\s+)[^.!?]*\bAppendix\s+\d+\b[^.!?]*(?:[.!?]|$)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return _sentence_case(cleaned.strip())


def _answer_looks_like_service_status(answer: str) -> bool:
    normalized = _normalize_search_text(answer)
    return bool(
        re.search(
            r"\bmodel service\b.*\b(?:busy|unavailable|starting|reached|try again)\b",
            normalized,
        )
        or re.search(
            r"\b(?:temporarily busy|temporarily unavailable|try again in a moment)\b",
            normalized,
        )
    )


def _remove_source_attribution_phrasing(text: str) -> str:
    source_name = (
        r"(?:the\s+)?(?:[A-Z]{2,}(?:\s+[A-Z]{2,}){0,4}|"
        r"[A-Z][A-Za-z0-9&./'()+-]*(?:\s+(?:[A-Z][A-Za-z0-9&./'()+-]*|for|of|and|the|in)){1,12}"
        r"(?:\s+\([A-Z][A-Z0-9&./+-]{1,12}\))?)"
    )
    cleaned = re.sub(
        rf"(?:^|(?<=[.!?])\s+)[^.!?]*\b{source_name}\b[^.!?]*\b"
        r"(?:has\s+)?(?:consistently\s+)?(?:supported|endorsed)\s+"
        r"(?:the\s+)?(?:adoption|use)\b[^.!?]*(?:[.!?]|$)",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+(?:using|the use of)\b",
        "use",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+initiating\b",
        "initiate",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+starting\b",
        "start",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:guidelines?|recommendations?|guidance)"
        r"(?:\s+(?:from|in)\s+\d{4})?\s+"
        r"(?:recommends?|suggests?|advises?)\s+"
        r"([^.!?\n]{1,180}?)\s+due\s+to\s+",
        r"\1 is recommended due to ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:guidelines?|recommendations?|guidance)"
        r"(?:\s+(?:from|in)\s+\d{4})?\s+"
        r"(?:recommends?|suggests?|advises?)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+"
        r"([^.!?\n]{1,220}?)\s+as\s+(?:the\s+)?preferred\b",
        r"\1 is preferred as",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b([A-Za-z][A-Za-z/-]*s)\s+is\s+preferred\b",
        r"\1 are preferred",
        cleaned,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+"
        r"([^.!?\n]{1,220}?)\s+as\s+",
        r"\1 is recommended as ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+"
        r"((?:an?|the)\s+)",
        r"\1",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:recommends?|suggests?|advises?)\s+that\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{source_name}\s+(?:states?|reports?|notes?|indicates?)\s+that\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"(?:^|(?<=[.!?])\s+){source_name}\s+"
        r"(?:updated|published|issued|provides?|offers?|describes?|discusses?)\b"
        r"[^.!?]*(?:[.!?]|$)\s*",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _sentence_case(text: str) -> str:
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return text
    index = match.start()
    return f"{text[:index]}{text[index].upper()}{text[index + 1:]}"


def _normalize_answer_spacing(text: str) -> str:
    cleaned = text.replace("\u00a0", " ").replace("\u00ad", "")
    cleaned = re.sub(r"([A-Za-z])-+\s*\n\s*([a-z])", r"\1\2", cleaned)
    cleaned = re.sub(r"([,;:])(?=[A-Za-z])", r"\1 ", cleaned)
    cleaned = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[a-z])(?=[A-Z][a-z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z0-9])(\[\d{1,2}\])", r" \1", cleaned)
    cleaned = re.sub(r"(\[\d{1,2}\])(?=[A-Za-z])", r"\1 ", cleaned)
    cleaned = re.sub(r"\b(and|or|for|with|during|after|before|between|among)(?=[A-Z])", r"\1 ", cleaned)
    cleaned = re.sub(
        r"\b([A-Z][A-Za-z]{7,}(?:\s+[A-Z][A-Za-z]{2,}){0,4})(of|for|and|in)(?=\s+[A-Z])",
        r"\1 \2",
        cleaned,
    )
    cleaned = re.sub(r"\b(\d+)\s?(kg|mg|g|mcg|ml)\b", r"\1 \2", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip()


def _format_answer_body(answer: str) -> str:
    cleaned = _normalize_answer_spacing(answer)
    cleaned = re.sub(r"(?<!\n)\n(#{1,6}\s)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"(#{1,6}[^\n]+)\n(?!\n)", r"\1\n\n", cleaned)
    blocks = re.split(r"\n{2,}", cleaned)
    formatted_blocks = [_paragraphize_block(block.strip()) for block in blocks if block.strip()]
    return "\n\n".join(block for block in formatted_blocks if block)


def _paragraphize_block(block: str) -> str:
    if _is_structured_markdown_block(block):
        return block
    sentences = re.split(r"(?<=[.!?])\s+(?=(?:\*\*)?[A-Z0-9])", block)
    if len(sentences) <= 1:
        return block

    paragraphs: list[str] = []
    current: list[str] = []
    current_length = 0
    for sentence in sentences:
        stripped = sentence.strip()
        if not stripped:
            continue
        projected_length = current_length + len(stripped) + (1 if current else 0)
        if current and (projected_length > 260 or len(current) >= 2):
            paragraphs.append(" ".join(current))
            current = [stripped]
            current_length = len(stripped)
            continue
        current.append(stripped)
        current_length = projected_length
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _is_structured_markdown_block(block: str) -> bool:
    stripped = block.lstrip()
    return bool(
        stripped.startswith(("#", "-", "*", ">"))
        or re.match(r"\d+\.\s", stripped)
        or "|" in stripped and "\n" in stripped
    )


def _metadata_only_note(item: dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    if str(raw.get("retrieval_mode") or "").strip().lower() != "pdf_seed_metadata":
        return ""
    return (
        "Evidence: Trusted source link discovered by live Crawl4AI metadata search; "
        "full document text was not extracted in this request."
    )


def _source_key(item: dict[str, Any]) -> str:
    source = item.get("source") or ""
    return str(source.get("value") if isinstance(source, dict) else source).strip().lower()


def _year_from_publication_date(value: object) -> object:
    if not value:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", str(value))
    return int(match.group(0)) if match else None


def _compact_text(text: str, max_length: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def _query_focused_snippet(text: str, query: str, max_length: int) -> str:
    compact = " ".join(text.split())
    if not compact:
        return ""

    query_terms = set(_snippet_focus_terms(query))
    if not query_terms:
        return _compact_text(compact, max_length)

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if sentence.strip()
    ]
    if len(sentences) <= 1:
        return _compact_text(compact, max_length)

    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        score = _snippet_sentence_score(sentence, query_terms)
        if score > 0:
            scored.append((score, index, sentence))

    if not scored:
        return _compact_text(compact, max_length)

    selected_indexes = sorted(index for _score, index, _sentence in sorted(scored, reverse=True)[:3])
    selected: list[str] = []
    current_length = 0
    for index in selected_indexes:
        sentence = sentences[index]
        projected = current_length + len(sentence) + (1 if selected else 0)
        if selected and projected > max_length:
            break
        selected.append(sentence)
        current_length = projected
    return _compact_text(" ".join(selected) or compact, max_length)


def _snippet_sentence_score(sentence: str, query_terms: set[str]) -> int:
    sentence_terms = set(re.findall(r"[a-z0-9]{3,}", sentence.lower()))
    overlap = sum(1 for term in query_terms if _term_matches_text_terms(term, sentence_terms))
    normalized = _normalize_search_text(sentence)
    signal = sum(
        1
        for pattern in SNIPPET_ANSWER_SIGNAL_PATTERNS
        if re.search(pattern, normalized)
    )
    if "+" in sentence or re.search(r"\([A-Za-z0-9/+-]{2,}\)", sentence):
        signal += 2
    metadata_penalty = sum(
        3
        for pattern in SNIPPET_METADATA_PATTERNS
        if re.search(pattern, normalized)
    )
    if {"first", "initial", "standard"}.intersection(query_terms):
        metadata_penalty += sum(
            3
            for pattern in SNIPPET_NON_INITIAL_PATTERNS
            if re.search(pattern, normalized)
        )
    return overlap * 4 + signal - metadata_penalty


def _term_matches_text_terms(term: str, text_terms: set[str]) -> bool:
    if term in text_terms:
        return True
    if len(term) > 4 and term.endswith("s") and term[:-1] in text_terms:
        return True
    return any(
        len(candidate) > 4 and candidate.endswith("s") and candidate[:-1] == term
        for candidate in text_terms
    )


def _role_instruction(user_role_from_db: Optional[str]) -> str:
    if not user_role_from_db:
        return ROLE_INSTRUCTIONS["DEFAULT"]
    mapping = {
        "Consultant": ROLE_INSTRUCTIONS["EXPERT"],
        "Specialist": ROLE_INSTRUCTIONS["EXPERT"],
        "Senior House Officer": ROLE_INSTRUCTIONS["CLINICIAN"],
        "Senior House Officers": ROLE_INSTRUCTIONS["CLINICIAN"],
        "Medical Officer": ROLE_INSTRUCTIONS["CLINICIAN"],
        "Clinical Officer": ROLE_INSTRUCTIONS["CLINICIAN"],
        "Other Clinical Practitioner": ROLE_INSTRUCTIONS["CLINICIAN"],
        "Intern Clinician": ROLE_INSTRUCTIONS["TRAINEE"],
        "Intern Doctor": ROLE_INSTRUCTIONS["TRAINEE"],
        "Clinical/Medical Student": ROLE_INSTRUCTIONS["STUDENT"],
        "Student": ROLE_INSTRUCTIONS["STUDENT"],
    }
    return mapping.get(user_role_from_db, ROLE_INSTRUCTIONS["DEFAULT"])


def _ensure_reference_urls(answer: str, citations: list[dict[str, object]]) -> str:
    if not citations:
        return _format_answer_body(answer)
    answer_without_references = re.split(
        r"\n\s*(?:\*\*)?References(?:\*\*)?\s*\n",
        answer,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].rstrip()
    answer_without_references = _format_answer_body(answer_without_references)
    answer_without_references, citations = _compact_used_citations(answer_without_references, citations)
    answer_without_references = _link_inline_reference_markers(answer_without_references, citations)

    lines = ["", "", "**References**", ""]
    for index, citation in enumerate(citations, start=1):
        lines.append(_format_reference_line(index, citation))
    return answer_without_references + "\n".join(lines)


def _format_reference_line(index: int, citation: dict[str, object]) -> str:
    title = _markdown_escape(_clean_reference_title(str(citation.get("title") or f"Source {index}")))
    url = str(citation.get("url") or "").strip()
    source = _markdown_escape(str(citation.get("source_label") or "")).strip()
    year = citation.get("year")
    metadata_parts = [source, str(year)] if source and year else []
    if not url and source and not year:
        metadata_parts = [source]
    metadata = ", ".join(metadata_parts)

    if url and metadata:
        return f"{index}. [{title}]({url}) - {metadata} - {url}"
    if url:
        return f"{index}. [{title}]({url}) - {url}"
    if metadata:
        return f"{index}. {title} - {metadata}"
    return f"{index}. {title}"


def _link_inline_reference_markers(
    answer: str,
    citations: list[dict[str, object]],
) -> str:
    if not answer or not citations:
        return answer

    url_by_number = {
        str(index): str(citation.get("url") or "").strip()
        for index, citation in enumerate(citations, start=1)
    }

    def replace_marker(match: re.Match[str]) -> str:
        replacements: list[str] = []
        for raw_number in match.group(1).split(","):
            number = raw_number.strip()
            url = url_by_number.get(number, "")
            replacements.append(f"[{number}]({url})" if url else f"[{number}]")
        return " ".join(replacements)

    return re.sub(
        r"(?<!\[)\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\](?![\]\(])",
        replace_marker,
        answer,
    )


async def _polish_answer_body_with_model(
    *,
    query: str,
    answer: str,
    deep_search: bool,
) -> str:
    if not _answer_polish_enabled() or not answer.strip():
        return answer
    answer_body = re.split(
        r"\n\s*(?:\*\*)?References(?:\*\*)?\s*\n",
        answer,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    if not answer_body:
        return answer

    prompt = f"""
Rewrite this medical answer body for scope and clarity only.

User question:
{query}

Draft answer body:
{answer_body}

Rules:
- Return only the revised answer body, not a References section.
- Keep only points that directly answer the user's question.
- Start with the clinical answer, not source or guideline descriptions.
- Remove publisher/source prose and similar attribution wording.
- Do not add new medical facts, new citations, or new references.
- Preserve numeric citation markers like [1] on claims that remain.
- Keep the answer concise and medically useful.
""".strip()
    payload = {
        "prompt": prompt,
        "prompt_type": "empirico_answer_polish",
        "temperature": 0.0,
        "max_output_tokens": min(1200 if deep_search else 900, max(400, len(answer_body) + 200)),
        "top_p": 0.8,
        "top_k": 20,
        "candidate_count": 1,
        "require_evidence": False,
    }
    try:
        data = await _post_model_response(
            payload,
            timeout_seconds=_answer_polish_timeout(),
        )
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        logger.debug("Answer polish fell back to original body: %s", exc)
        return answer_body

    polished = str(data.get("answer") or "").strip()
    if not polished or _answer_looks_like_service_status(polished):
        return answer_body
    if not re.search(r"\[\d+\]", polished) and re.search(r"\[\d+\]", answer_body):
        return answer_body
    return polished


def _clean_reference_title(title: str) -> str:
    cleaned = _normalize_answer_spacing(title)
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\s*\|\s*", " | ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^\d+(?:\.\d+){1,4}\s+", "", cleaned)
    return cleaned.strip() or "Source"


def _compact_used_citations(
    answer: str,
    citations: list[dict[str, object]],
) -> tuple[str, list[dict[str, object]]]:
    citation_by_original_number = {
        str(index): citation for index, citation in enumerate(citations, start=1)
    }
    remapped_numbers: dict[str, int] = {}
    used_original_numbers: list[str] = []

    def remap_number(original: str) -> int | None:
        if original not in citation_by_original_number:
            return None
        if original not in remapped_numbers:
            remapped_numbers[original] = len(remapped_numbers) + 1
            used_original_numbers.append(original)
        return remapped_numbers[original]

    normalized = re.sub(r"\[\[(\d{1,2})\]\](?!\()", r"[\1]", answer)

    def replace_marker(match: re.Match[str]) -> str:
        originals = [part.strip() for part in match.group(1).split(",")]
        replacements: list[str] = []
        for original in originals:
            next_number = remap_number(original)
            if next_number is not None:
                replacements.append(f"[{next_number}]")
        return " ".join(replacements) if replacements else ""

    normalized = re.sub(
        r"(?<!\[)\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\](?:\([^)]*\))?(?!\])",
        replace_marker,
        normalized,
    )
    if not used_original_numbers:
        return answer, citations

    compacted_citations: list[dict[str, object]] = []
    for number in used_original_numbers:
        citation = dict(citation_by_original_number[number])
        citation["number"] = remapped_numbers[number]
        compacted_citations.append(citation)
    return normalized, compacted_citations


async def _generate_followup_questions(query: str, answer: str, *, deep_search: bool = False) -> list[str]:
    mode = os.getenv("EMPIRICO_FOLLOWUP_MODE", "local").strip().lower()
    if mode in {"off", "false", "0", "none", "disabled"}:
        return []
    if mode not in {"model", "llm", "remote"}:
        return _local_followup_questions(query, answer)

    prompt = f"""
Generate exactly 3 concise follow-up questions a medical information user might ask next.

Original question:
{query[:500]}

Answer:
{answer[:1800]}

Rules:
- Output only the 3 questions.
- One question per line.
- No intro text.
- Do not include citations.
""".strip()
    payload = {
        "prompt": prompt,
        "prompt_type": "empirico_followup_questions",
        "temperature": 0.35,
        "max_output_tokens": 400,
        "top_p": 0.9,
        "top_k": 20,
        "candidate_count": 1,
    }
    try:
        data = await _post_model_response(
            payload,
            timeout_seconds=min(_model_timeout_for_mode(deep_search), 4.0),
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Could not generate follow-up questions via model service: %s", exc)
        return _local_followup_questions(query, answer)

    text = re.sub(r"-\s*\n\s*", "-", str(data.get("answer") or ""))
    questions: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"^[\s\d.\-*)]+", "", line).strip()
        if not cleaned:
            continue
        if len(cleaned) < 12 or "follow-up" in cleaned.lower():
            continue
        if not cleaned.endswith("?"):
            cleaned = cleaned.rstrip(" .;:") + "?"
        if re.search(r"-\?$", cleaned):
            continue
        questions.append(cleaned)
        if len(questions) == 3:
            break
    return questions


def _local_followup_questions(query: str, answer: str) -> list[str]:
    return [
        "What alternatives should be considered if the first plan is unsuitable?",
        "What contraindications, cautions, or red flags should be checked?",
        "What monitoring or follow-up is recommended?",
    ]


async def _search_local_evidence(
    *,
    query: str,
    top_k: int,
    country_code: Optional[str],
    deep_search: bool,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _run_local_evidence_search,
        query,
        top_k,
        country_code,
        _local_evidence_provider_mode(deep_search),
        deep_search,
    )


def _run_local_evidence_search(
    query: str,
    top_k: int,
    country_code: Optional[str],
    provider_mode: str,
    deep_search: bool,
) -> dict[str, Any]:
    effective_country_code = None if (country_code or "").upper() == "GLOBAL" else country_code
    try:
        result = EvidenceSearchService(
            settings=_search_settings_for_mode(deep_search),
            country_code=effective_country_code,
            provider_mode=provider_mode,
        ).search(query, top_k=top_k)
    except Exception as exc:
        logger.error("Local evidence retrieval failed: %s", exc, exc_info=True)
        return {"items": [], "provider_errors": [str(exc)], "timings_ms": {}}

    return {
        "items": [item.model_dump(mode="json") for item in result.items],
        "provider_errors": result.provider_errors,
        "timings_ms": result.timings_ms,
    }


def _evidence_country_code_for_search() -> Optional[str]:
    raw = (
        os.getenv("EMPIRICO_EVIDENCE_COUNTRY_CODE")
        or os.getenv("EMPIRICO_MODEL_SERVICE_COUNTRY_CODE")
        or ""
    ).strip()
    if raw.lower() in {"", "none", "null", "off", "false", "0"}:
        return None
    return raw.upper()


def _broad_evidence_country_code(country_code: Optional[str]) -> str:
    return "GLOBAL" if (country_code or "").upper() != "GLOBAL" else "GLOBAL"


def _local_evidence_provider_mode(deep_search: bool) -> str:
    mode_key = (
        "EMPIRICO_DEEP_EVIDENCE_PROVIDER_MODE"
        if deep_search
        else "EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE"
    )
    default = "web" if deep_search else "crawl"
    raw = (
        os.getenv(mode_key)
        or os.getenv("EMPIRICO_EVIDENCE_PROVIDER_MODE")
        or default
    ).strip().lower()
    if raw in {"crawl", "crawled", "crawler", "web_crawl", "crawl_only"}:
        return "crawl"
    return "web"


def _source_preference_hints() -> str:
    raw = os.getenv("EMPIRICO_SOURCE_PREFERENCE_HINTS")
    if raw is None:
        return DEFAULT_SOURCE_PREFERENCE_HINTS
    return " ".join(raw.split())


def _source_preference_terms() -> tuple[str, ...]:
    raw = os.getenv("EMPIRICO_SOURCE_PREFERENCE_TERMS")
    if raw is None:
        return DEFAULT_SOURCE_PREFERENCE_TERMS
    terms = [
        _normalize_search_text(term)
        for term in re.split(r"[,;\n]+", raw)
        if term.strip()
    ]
    return tuple(dict.fromkeys(term for term in terms if term))


def _active_source_preference_terms(
    query_context: str,
    source_preference_terms: tuple[str, ...],
) -> tuple[str, ...]:
    if not _query_mentions_source_preference(query_context, source_preference_terms):
        return ()
    return source_preference_terms


def _answer_polish_enabled() -> bool:
    raw = os.getenv("EMPIRICO_ENABLE_ANSWER_POLISH", "false").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _answer_polish_timeout() -> float:
    return _env_float(
        "EMPIRICO_ANSWER_POLISH_TIMEOUT_SECONDS",
        45.0,
        minimum=10.0,
        maximum=90.0,
    )


def _markdown_escape(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|])", r"\\\1", value)


async def _post_model_response(
    payload: dict[str, Any],
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    base_url = _model_service_base_url()
    timeout = timeout_seconds or _env_float(
        "MODEL_SERVICE_TIMEOUT_SECONDS",
        120.0,
        minimum=30.0,
        maximum=300.0,
    )
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("MODEL_SERVICE_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await asyncio.wait_for(
                client.post(
                    f"{base_url}{_model_service_response_path()}",
                    headers=headers,
                    json=payload,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise httpx.ReadTimeout(f"model service exceeded {timeout:.1f}s") from exc
        response.raise_for_status()
        return _normalize_model_service_response(response.json())


def _model_service_base_url() -> str:
    return (
        os.getenv("MODEL_SERVICE_BASE_URL")
        or os.getenv("EMPIRICO_MODEL_SERVICE_URL")
        or DEFAULT_MODEL_SERVICE_BASE_URL
    ).rstrip("/")


def _model_service_response_path() -> str:
    raw = (os.getenv("MODEL_SERVICE_RESPONSE_PATH") or "/v1/model/respond").strip()
    if not raw:
        return "/v1/model/respond"
    return raw if raw.startswith("/") else f"/{raw}"


def _normalize_model_service_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("model service response must be a JSON object")

    normalized = dict(data)
    nested_data = normalized.get("data")
    if isinstance(nested_data, dict):
        normalized = {**normalized, **nested_data}

    answer = _extract_model_answer(normalized)
    if answer:
        normalized["answer"] = answer
    return normalized


def _extract_model_answer(data: dict[str, Any]) -> str:
    for key in (
        "answer",
        "model_response",
        "response",
        "content",
        "text",
        "output_text",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    choices = data.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            text = choice.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    candidates = data.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            text = _extract_vertex_candidate_text(candidate)
            if text:
                return text

    return ""


def _extract_vertex_candidate_text(candidate: Any) -> str:
    if not isinstance(candidate, dict):
        return ""
    content = candidate.get("content")
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            text_parts = [
                str(part.get("text")).strip()
                for part in parts
                if isinstance(part, dict) and part.get("text")
            ]
            if text_parts:
                return "\n".join(text_parts).strip()
    text = candidate.get("text")
    return text.strip() if isinstance(text, str) else ""


def _safe_response_text(response: httpx.Response) -> str:
    text = response.text.strip()
    if len(text) > 500:
        return text[:500] + "..."
    return text
