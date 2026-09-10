"""
Adapter for routing Empirico knowledge answers through the standalone model
service.

"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Optional
from urllib.parse import quote, urlparse

import httpx

from healthnavi.core.constants import (
    DEEP_SEARCH_MAX_OUTPUT_TOKENS,
    QUICK_SEARCH_MAX_OUTPUT_TOKENS,
)
from healthnavi.services.answer_composer import (
    build_answer_prompt,
    citation_document_key,
    citation_location_key,
    clean_reference_title,
    finalize_answer,
)
from healthnavi.evidence_retrieval.services.evidence_search_service import (
    EvidenceSearchService,
)
from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings, get_settings
from healthnavi.evidence_retrieval.services.clinical_specificity import (
    clinical_specificity_score,
)
from healthnavi.evidence_retrieval.services.evidence_policy import (
    evidence_policy_sort_key,
)

logger = logging.getLogger(__name__)
DEFAULT_MODEL_SERVICE_BASE_URL = "https://empirico-model-service-e2dgjxq3uq-ew.a.run.app"
USER_SAFE_GENERATION_ERROR = "I couldn't complete this answer right now. Please try again."
DEFAULT_QUICK_LATENCY_TARGET_SECONDS = 14.5
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
DEFAULT_QUICK_ANSWER_SOURCES = 4
DEFAULT_DEEP_ANSWER_SOURCES = 8
DEFAULT_SOURCE_PREFERENCE_HINTS = (
    "Uganda Ministry of Health Knowledge Management Portal, Uganda Clinical Guidelines, "
    "National Drug Authority Uganda, UNIPH, CPHL/NHLDS, Uganda specialist institutions, "
    "WHO AFRO, East Africa, and Africa before global fallback sources when relevant"
)
DEFAULT_SOURCE_PREFERENCE_TERMS: tuple[str, ...] = (
    "uganda",
    "ugandan",
    "health.go.ug",
    "library.health.go.ug",
    "nda.or.ug",
    "uniph.go.ug",
    "cphl.go.ug",
    "qadash.cphl.go.ug",
    "uci.or.ug",
    "ulii.org",
    "idi.mak.ac.ug",
    "elearning.idi.co.ug",
    "uganda clinical guidelines",
    "ministry of health uganda",
    "national drug authority uganda",
    "uganda national institute of public health",
    "uganda cancer institute",
    "who afro",
    "afro.who.int",
    "east africa",
    "africa",
)
LOCAL_SOURCE_PREFERENCE_TERMS = {
    "uganda",
    "ugandan",
    "health.go.ug",
    "library.health.go.ug",
    "nda.or.ug",
    "uniph.go.ug",
    "cphl.go.ug",
    "qadash.cphl.go.ug",
    "uci.or.ug",
    "ulii.org",
    "idi.mak.ac.ug",
    "elearning.idi.co.ug",
    "uganda clinical guidelines",
    "ministry of health uganda",
    "national drug authority uganda",
    "uganda national institute of public health",
    "uganda cancer institute",
}
REGIONAL_SOURCE_PREFERENCE_TERMS = {
    "who afro",
    "afro.who.int",
    "east africa",
    "africa",
}
ALTERNATE_JURISDICTION_TERMS = {
    "kenya",
    "kenyan",
    "tanzania",
    "tanzanian",
    "rwanda",
    "rwandan",
    "burundi",
    "burundian",
    "south sudan",
    "sudan",
    "ethiopia",
    "ethiopian",
    "eritrea",
    "congo",
    "drc",
    "democratic republic of congo",
    "zambia",
    "zambian",
    "malawi",
    "malawian",
    "south africa",
    "south african",
    "nigeria",
    "nigerian",
    "ghana",
    "ghanaian",
    "india",
    "indian",
    "united states",
    "usa",
    "u s",
    "u s a",
    "america",
    "american",
    "canada",
    "canadian",
    "united kingdom",
    "uk",
    "u k",
    "britain",
    "british",
    "england",
    "europe",
    "european",
    "australia",
    "australian",
}
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
    r"\b(?:pico questions?|gdg|guideline development|evidence-to-decision|analytic framework)\b",
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
    "nda.or.ug",
    "uniph.go.ug",
    "platform.who.int",
    "cphl.go.ug",
    "qadash.cphl.go.ug",
    "uci.or.ug",
    "ulii.org",
)
SOURCE_LABELS = {
    "crawl4ai": "Guideline page",
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
    question_plan, retrieval_queries = await _evidence_request_plan_for_request(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        deep_search=deep_search,
    )
    requires_multi_branch_coverage = _question_plan_requires_multi_branch_coverage(question_plan)
    quick_latency_deadline = _quick_latency_deadline(
        deep_search,
        multi_branch=requires_multi_branch_coverage,
    )
    configured_source_preference_terms = _source_preference_terms()
    source_preference_context = " ".join((query, patient_data, chat_history))
    source_preference_terms = _active_source_preference_terms(
        source_preference_context,
        configured_source_preference_terms,
    )

    topic_hint = _question_topic_hint(question_plan)
    evidence_search_result = await _search_retrieval_queries(
        queries=retrieval_queries,
        top_k=search_top_k,
        country_code=country_code,
        deep_search=deep_search,
        source_preference_terms=source_preference_terms,
        answer_top_k=answer_top_k,
        coverage_required=requires_multi_branch_coverage,
        topic_hint=topic_hint,
    )
    provider_errors = list(evidence_search_result.get("provider_errors") or [])
    evidence_timings = dict(evidence_search_result.get("timings_ms") or {})
    raw_evidence = list(evidence_search_result.get("items") or [])
    evidence = _answer_candidates(
        raw_evidence,
        query=query,
        source_preference_terms=source_preference_terms,
        deep_search=deep_search,
        topic_hint=topic_hint,
    )
    citations = _citations_from_evidence(evidence)

    if not citations:
        # An answer without references is the one outcome we do not accept, so
        # this retry ignores the latency budget and the provider mode.
        rescue_result = await _rescue_evidence_search(
            queries=retrieval_queries,
            top_k=search_top_k,
            country_code=country_code,
            deep_search=deep_search,
            answer_top_k=answer_top_k,
            latency_deadline=quick_latency_deadline,
            topic_hint=topic_hint,
            required=True,
        )
        rescue_items = list(rescue_result.get("items") or [])
        if rescue_items:
            provider_errors.extend(list(rescue_result.get("provider_errors") or []))
            evidence_timings["rescue"] = rescue_result.get("timings_ms") or {}
            raw_evidence = _merge_evidence_items(raw_evidence, rescue_items)
            evidence = _answer_candidates(
                raw_evidence,
                query=query,
                source_preference_terms=source_preference_terms,
                deep_search=deep_search,
                topic_hint=topic_hint,
            )
            citations = _citations_from_evidence(evidence)

    if not citations:
        logger.error(
            "Answering without references, every retrieval path returned nothing: "
            "country_code=%s raw_items=%d provider_errors=%s",
            country_code or "global",
            len(raw_evidence),
            provider_errors,
        )
        sources: list[dict[str, Any]] = []
        evidence = []
    else:
        sources = _answer_sources(evidence, citations, deep_search=deep_search, query=query)
        logger.info(
            "Answer sources (%s): %s",
            "deep" if deep_search else "quick",
            [f"[{s['number']}] {str(s.get('title') or '')[:70]} <{s.get('url')}>" for s in sources],
        )

    prompt = build_answer_prompt(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        deep_search=deep_search,
        user_role_from_db=user_role_from_db,
        sources=sources,
        max_references=_max_references(deep_search),
    )
    data = await _generate_answer_with_model(
        prompt=prompt,
        prompt_type=prompt_type if sources else f"{prompt_type}_no_references",
        deep_search=deep_search,
    )
    raw_answer = str(data.get("answer") or "").strip()
    answer, used_citations = finalize_answer(raw_answer, sources, max_references=_max_references(deep_search))
    followup_questions = await _generate_followup_questions(query, answer, deep_search=deep_search)

    logger.info(
        "Model service response completed: model=%s country_code=%s citations=%d/%d raw_evidence=%d provider_errors=%d timings=%s",
        data.get("model"),
        country_code or "global",
        len(used_citations),
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
        True,
        str(data.get("prompt_type") or prompt_type),
        followup_questions,
    )


class AnswerGenerationError(RuntimeError):
    """The model service could not produce an answer after retries."""


def _answer_sources(
    evidence: list[dict[str, Any]],
    citations: list[dict[str, object]],
    *,
    deep_search: bool,
    query: str,
) -> list[dict[str, Any]]:
    """Pair each numbered citation with the evidence excerpt the model should read.

    ``citations`` was produced from ``evidence`` in order, skipping items without a
    URL, so walk the evidence in the same order and keep the numbering aligned.
    """
    excerpt_limit = 2800 if deep_search else 1800
    sources: list[dict[str, Any]] = []
    index_by_location: dict[str, int] = {}
    first_number_by_document: dict[str, int] = {}
    citation_index = 0
    for item in evidence:
        if citation_index >= len(citations):
            break
        record = _normalize_evidence_record(item)
        if record is None:
            continue
        citation = citations[citation_index]
        citation_index += 1
        raw_excerpt = str(item.get("abstract") or item.get("snippet") or "")
        if len(" ".join(raw_excerpt.split())) > excerpt_limit and not deep_search:
            retrieval_query = _evidence_record_retrieval_query(item) or ""
            excerpt = _query_focused_snippet(raw_excerpt, f"{query} {retrieval_query}", excerpt_limit)
        else:
            excerpt = _compact_text(raw_excerpt, excerpt_limit)

        location = citation_location_key(str(citation.get("url") or ""))
        existing_index = index_by_location.get(location)
        if existing_index is not None:
            # Same document location (page or web page): one numbered source, several excerpts.
            existing = sources[existing_index]
            if excerpt and excerpt not in existing["excerpt"]:
                existing["excerpt"] = _compact_text(
                    f"{existing['excerpt']} [...] {excerpt}" if existing["excerpt"] else excerpt,
                    excerpt_limit * 2,
                )
            continue
        index_by_location[location] = len(sources)
        document = citation_document_key(str(citation.get("url") or ""))
        source: dict[str, Any] = {
            "number": len(sources) + 1,
            "title": citation.get("title"),
            "source_label": citation.get("source_label"),
            "year": citation.get("year"),
            "url": citation.get("url"),
            "excerpt": excerpt,
        }
        first_number = first_number_by_document.get(document)
        if first_number is not None:
            source["same_document_as"] = first_number
        else:
            first_number_by_document[document] = source["number"]
        sources.append(source)
    return sources


async def _generate_answer_with_model(
    *,
    prompt: str,
    prompt_type: str,
    deep_search: bool,
) -> dict[str, Any]:
    """Call the model service once, retrying a single time on transient failure.

    The answer call always gets the full per-mode timeout. Retrieval-side steps
    are the ones bounded by the quick latency target; starving the answer call
    is what produced unusable fallback text in the past.
    """
    payload = {
        "prompt": prompt,
        "prompt_type": prompt_type,
        "temperature": _answer_temperature(),
        "max_output_tokens": _max_output_tokens_for_mode(deep_search),
        "top_p": 0.95,
        "candidate_count": 1,
        "require_evidence": False,
    }
    model_name = _model_name_for_mode(deep_search)
    if model_name:
        payload["model"] = model_name

    timeout_seconds = _model_timeout_for_mode(deep_search)
    last_error: str | None = None
    for attempt in range(2):
        try:
            data = await _post_model_response(payload, timeout_seconds=timeout_seconds)
        except httpx.HTTPStatusError as exc:
            last_error = f"HTTP {exc.response.status_code}: {_safe_response_text(exc.response)}"
            logger.error("Model service returned %s (attempt %d)", last_error, attempt + 1)
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                break
        except (httpx.RequestError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.error("Model service request failed (attempt %d): %s", attempt + 1, exc)
        else:
            answer = str(data.get("answer") or "").strip()
            if answer and not _answer_looks_like_service_status(answer):
                return data
            last_error = f"unusable answer: {answer[:160]!r} provider_errors={data.get('provider_errors')}"
            logger.warning("Model service returned no usable answer (attempt %d): %s", attempt + 1, last_error)
        if attempt == 0:
            await asyncio.sleep(1.5 if deep_search else 0.75)
    raise AnswerGenerationError(last_error or "model service did not return an answer")


def _answer_temperature() -> float:
    return _env_float("EMPIRICO_ANSWER_TEMPERATURE", 0.2, minimum=0.0, maximum=1.0)


async def _retrieval_queries_for_request(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
) -> tuple[str, ...]:
    _question_plan, retrieval_queries = await _evidence_request_plan_for_request(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        deep_search=deep_search,
    )
    return retrieval_queries


async def _evidence_request_plan_for_request(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    fallback = _fallback_retrieval_queries(query, deep_search=deep_search)
    fallback_plan = _fallback_question_plan(query)
    if not fallback:
        return fallback_plan, ("clinical medicine",)
    if not _retrieval_planner_enabled(deep_search):
        return fallback_plan, fallback

    payload = {
        "prompt": _build_evidence_request_planning_prompt(
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
        return fallback_plan, fallback

    question_plan = _question_plan_from_model_response(data, query=query)
    planned = _retrieval_queries_from_question_plan(question_plan)
    if not planned:
        planned = _retrieval_queries_from_model_response(data)
    planned_limit = 4 if deep_search else 3
    planned = _augment_planned_queries_with_coverage_goal(
        query=query,
        question_plan=question_plan,
        planned=planned,
        deep_search=deep_search,
    )
    retrieval_queries = _prioritized_retrieval_queries(
        query=query,
        planned=planned[:planned_limit],
        fallback=fallback,
        deep_search=deep_search,
    ) or fallback
    return question_plan, retrieval_queries


def _augment_planned_queries_with_coverage_goal(
    *,
    query: str,
    question_plan: dict[str, Any],
    planned: tuple[str, ...],
    deep_search: bool,
) -> tuple[str, ...]:
    """Add one query per uncovered answer facet, filling leftover slots only.

    The planner's own queries come first because it saw the whole question. Each
    facet becomes its own short query rather than being concatenated into one
    long string: a single query naming every requirement just repeats the topic
    words and returns the pages the first query already found.
    """
    facets = [
        *_clean_string_list(question_plan.get("answer_requirements"), limit=3),
        *_clean_string_list(question_plan.get("evidence_goals"), limit=2),
    ]
    if not facets:
        return planned

    anchor = _compact_text(
        _text_from_unknown(question_plan.get("condition"))
        or _text_from_unknown(question_plan.get("clinical_question"))
        or query,
        90,
    )
    population = _compact_text(_text_from_unknown(question_plan.get("population")) or "", 40)
    facet_queries = [
        _clean_retrieval_query(" ".join(part for part in (anchor, population, facet) if part))
        for facet in facets
    ]
    limit = 4 if deep_search else 3
    return _normalized_retrieval_queries([*planned, *facet_queries], limit=limit)


def _fallback_retrieval_queries(query: str, *, deep_search: bool) -> tuple[str, ...]:
    cleaned = " ".join(query.split())
    if not cleaned:
        return ()
    return _normalized_retrieval_queries([cleaned])


def _prioritized_retrieval_queries(
    *,
    query: str,
    planned: tuple[str, ...],
    fallback: tuple[str, ...],
    deep_search: bool,
) -> tuple[str, ...]:
    if not planned:
        return fallback

    original_query = fallback[:1]
    # Total retrieval queries per request, the user's own question included. Each
    # one costs a full crawl round, so quick search stays at three.
    planned_limit = 4 if deep_search else 3
    return _normalized_retrieval_queries(
        [*original_query, *planned[:planned_limit], *fallback[1:]],
        limit=planned_limit,
    )


def _build_retrieval_query_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
) -> str:
    return _build_evidence_request_planning_prompt(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        deep_search=deep_search,
    )


def _build_evidence_request_planning_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
) -> str:
    max_queries = 4 if deep_search else 3
    return f"""
You understand medical questions and create an evidence request before retrieval.

Return only valid JSON in this shape:
{{
  "clinical_question": "the user's clinical question, preserving qualifiers",
  "task": "semantic clinical task",
  "population": "population if stated or implied, otherwise empty",
  "condition": "condition/exposure/intervention if applicable, otherwise empty",
  "jurisdiction": "requested jurisdiction if stated, otherwise empty",
  "requested_output": "what the answer must produce",
  "answer_requirements": ["requirement one", "requirement two"],
  "evidence_goals": ["goal one", "goal two"],
  "queries": ["query one", "query two"]
}}

Rules:
- Do not answer the medical question.
- Infer the clinical task semantically from the full question and context, not from keyword matching.
- Make answer_requirements the minimum evidence facets needed to answer this specific question correctly.
- Make evidence_goals describe the kinds of passages needed, such as recommendations, thresholds, differential explanations, interaction management, safety limits, or decision branches, but only when relevant to this question.
- Create 1 to {max_queries} concise web/library search queries.
- Order queries by direct usefulness to the final answer. Query 1 must be the direct-answer query most likely to retrieve the actual clinical option, regimen, dose, threshold, interpretation, or action.
- Every query after the first must target a different facet of the answer, not reword the first. Rewording wastes the retrieval budget because it returns the same pages. Facets differ by what the clinician needs next: how the choice between options is decided, the operative detail of the chosen option, a subgroup managed differently, or the endpoint such as monitoring, stopping, or discharge criteria.
- Preserve clinically relevant context from the user's wording, such as population, setting, jurisdiction, pregnancy, comorbidities, exposure, intervention, comparator, and outcome when present.
- Expand abbreviations or implicit clinical wording only when that would make retrieval clearer.
- If the user includes a city, country, region, or health system, include one query for local/national guidance and one direct clinical-answer query that omits the place when global guidance is likely to contain the regimen, dose, threshold, or standard recommendation.
- When the question asks for clinical action, use complementary queries when possible: one to find authoritative guidance, one to retrieve the direct answer, and one to verify any practical details needed to answer completely.
- Do not make the first query only a broad guideline landing-page query when the user needs a practical clinical answer. Put regimen, dose, threshold, adult/child/pregnancy, first-line/initial, or other task terms in query 1 when they are implied by the user question.
- If the answer may involve multiple parts, make sure one query is broad enough to retrieve the full set rather than only the most obvious anchor term.
- Match the verification query to the user's clinical task without inventing likely answer terms.
- Do not guess the answer's vocabulary. Build semantic query variants that retrieve and verify the answer from external evidence.
- Make one query target the operative level of detail the task needs, using generic wording such as dose, regimen, protocol, schedule, criteria, threshold, or steps. Retrieving the page that describes a service, programme, or pathway is not enough when the user needs what is actually given or done.
- If the user's population spans subgroups that are managed differently, such as an age range, pregnancy, or severity band, make sure the queries between them cover the whole range rather than only the largest subgroup.
- Avoid implementation, adherence, epidemiology, or burden wording unless the user asked for those.
- Prefer wording likely to retrieve current, authoritative medical sources that directly answer the question.
- Do not add source names, country names, conditions, or treatments that are not implied by the user question or context.

User question:
{query}

Context:
{patient_data or "No additional context provided."}

Previous conversation summary:
{chat_history or "No previous conversation."}
""".strip()


def _question_topic_hint(question_plan: dict[str, Any]) -> str:
    """What the question is about, for choosing which sources to crawl.

    The planner already separates the condition from the population and the
    requested output. A raw query string cannot: its rarest word is as likely to
    be "first-line" as "hypertension", and matching on that sends the crawler to
    whichever source happens to list the modifier as a topic.
    """
    condition = _text_from_unknown(question_plan.get("condition")) or ""
    if not condition.strip():
        # No planner, no condition, no hint. Falling back to the whole question
        # would be worse than having none: source selection treats a hint as the
        # subject and drops its safeguard against single-term matches, so the
        # question's rarest word decides, and that word is as likely to be
        # "first-line" as "hypertension".
        return ""
    return _compact_text(condition, 120)


def _fallback_question_plan(query: str) -> dict[str, Any]:
    return {
        "clinical_question": " ".join(query.split()),
        "task": "",
        "population": "",
        "condition": "",
        "jurisdiction": "",
        "requested_output": "",
        "answer_requirements": [],
        "evidence_goals": [],
        "queries": [],
    }


def _question_plan_from_model_response(
    data: dict[str, Any],
    *,
    query: str,
) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    answer = data.get("answer")
    if isinstance(answer, dict):
        parsed = answer
    elif isinstance(answer, str):
        parsed = _json_object_from_text(answer)
    if parsed is None:
        parsed = data

    plan = _fallback_question_plan(query)
    for key in (
        "clinical_question",
        "task",
        "population",
        "condition",
        "jurisdiction",
        "requested_output",
    ):
        value = _text_from_unknown(parsed.get(key))
        if value:
            plan[key] = value[:500]

    for key in ("answer_requirements", "evidence_goals", "queries"):
        plan[key] = _clean_string_list(parsed.get(key), limit=8 if key != "queries" else 4)

    return plan


def _retrieval_queries_from_question_plan(plan: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_clean_string_list(plan.get("queries"), limit=4))


def _clean_string_list(value: Any, *, limit: int) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        parsed = _json_object_from_text(value)
        if isinstance(parsed, dict):
            return _clean_string_list(parsed, limit=limit)
        raw_values = [value]
    elif isinstance(value, dict):
        raw_values = list(value.values())
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = []

    for item in raw_values:
        text = _text_from_unknown(item)
        if not text:
            continue
        cleaned = _compact_plain_text(text)[:220]
        if cleaned and cleaned not in values:
            values.append(cleaned)
        if len(values) >= limit:
            break
    return values


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


def _normalized_retrieval_queries(
    values: list[str] | tuple[str, ...],
    *,
    limit: int = 4,
) -> tuple[str, ...]:
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
        if len(queries) >= limit:
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
        return True
    normalized = raw.strip().lower()
    if normalized in {"auto", "adaptive"}:
        return True
    return normalized in {"1", "true", "yes", "on", "enabled"}


async def _search_retrieval_queries(
    *,
    queries: tuple[str, ...],
    top_k: int,
    country_code: Optional[str],
    deep_search: bool,
    provider_mode: str | None = None,
    source_preference_terms: tuple[str, ...] = (),
    answer_top_k: int | None = None,
    search_settings: EvidenceRetrievalSettings | None = None,
    coverage_required: bool = False,
    topic_hint: str | None = None,
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
                country_code=_country_code_for_retrieval_query(country_code, retrieval_query),
                deep_search=deep_search,
                provider_mode=provider_mode,
                search_settings=search_settings,
                topic_hint=topic_hint,
            )
        return index, retrieval_query, result

    query_jobs = list(enumerate(queries, start=1))
    query_results: list[tuple[int, str, dict[str, Any]]] = []
    running_tasks: list[asyncio.Task[tuple[int, str, dict[str, Any]]]] = []

    if _quick_retrieval_early_stop_enabled(
        deep_search=deep_search,
        provider_mode=provider_mode,
        query_count=len(query_jobs),
    ) and not coverage_required:
        first_job = query_jobs[0]
        query_jobs = query_jobs[1:]
        first_task = asyncio.create_task(run_query(*first_job))
        done, _pending = await asyncio.wait(
            {first_task},
            timeout=_quick_retrieval_early_stop_wait_seconds(),
        )
        if first_task in done:
            first_result = first_task.result()
            query_results.append(first_result)
            first_items = list(dict(first_result[2] or {}).get("items") or [])
            if _quick_retrieval_has_enough_answer_sources(
                items=first_items,
                query=first_result[1],
                source_preference_terms=source_preference_terms,
                answer_top_k=answer_top_k or DEFAULT_QUICK_ANSWER_SOURCES,
            ):
                timings["early_stop"] = True
                query_jobs = []
        else:
            running_tasks.append(first_task)

    if query_jobs or running_tasks:
        running_tasks.extend(
            asyncio.create_task(run_query(index, retrieval_query))
            for index, retrieval_query in query_jobs
        )
        query_results.extend(await asyncio.gather(*running_tasks))

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


def _quick_retrieval_early_stop_enabled(
    *,
    deep_search: bool,
    provider_mode: str | None,
    query_count: int,
) -> bool:
    if deep_search or provider_mode is not None or query_count < 2:
        return False
    raw = os.getenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP", "true").strip().lower()
    return raw not in {"0", "false", "off", "no", "none", "disabled"}


def _quick_retrieval_early_stop_wait_seconds() -> float:
    return _env_float(
        "EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP_WAIT_SECONDS",
        1.5,
        minimum=0.1,
        maximum=5.0,
    )


def _question_plan_requires_multi_branch_coverage(question_plan: dict[str, Any]) -> bool:
    """Avoid fast-path cancellation when the planner identified multiple answer facets."""
    requirements = _clean_string_list(question_plan.get("answer_requirements"), limit=6)
    goals = _clean_string_list(question_plan.get("evidence_goals"), limit=4)
    return len(requirements) > 1 or len(goals) > 1


def _quick_retrieval_has_enough_answer_sources(
    *,
    items: list[dict[str, Any]],
    query: str,
    source_preference_terms: tuple[str, ...],
    answer_top_k: int,
) -> bool:
    filtered = _filter_evidence_items(
        items,
        query=query,
        source_preference_terms=source_preference_terms,
    )
    return len(_unique_evidence_passages(filtered, limit=answer_top_k)) >= answer_top_k


async def _rescue_evidence_search(
    *,
    queries: tuple[str, ...],
    top_k: int,
    country_code: Optional[str],
    deep_search: bool,
    answer_top_k: int,
    latency_deadline: float | None = None,
    topic_hint: str | None = None,
    required: bool = False,
) -> dict[str, Any]:
    """Retry retrieval more broadly.

    ``required`` means the answer currently has no references at all. Every
    reason to hold back - the latency budget, the deployment's provider mode,
    the country filter - is worth less than a citation, because an uncited
    answer is the one outcome a clinician cannot check.
    """
    if not required and not _evidence_rescue_enabled():
        return {"items": [], "provider_errors": [], "timings_ms": {}}
    current_mode = _local_evidence_provider_mode(deep_search)
    broad_country = None if required else _broad_evidence_country_code(country_code)
    if (
        not required
        and current_mode == "web"
        and (country_code or "").upper() in {"", "GLOBAL"}
    ):
        return {"items": [], "provider_errors": [], "timings_ms": {}}
    rescue_queries = _normalized_retrieval_queries(
        list(queries),
        limit=4 if deep_search else 3,
    )
    if not rescue_queries:
        return {"items": [], "provider_errors": [], "timings_ms": {}}
    search_settings = (
        None
        if required
        else _rescue_search_settings_for_latency_budget(
            deep_search=deep_search,
            latency_deadline=latency_deadline,
        )
    )
    if not required and latency_deadline is not None and search_settings is None:
        logger.info("Skipping evidence rescue because the quick latency budget is exhausted")
        return {"items": [], "provider_errors": [], "timings_ms": {"skipped": "latency_budget"}}
    logger.info(
        "Running evidence rescue search: mode=web country=%s required=%s queries=%s",
        broad_country or "global",
        required,
        rescue_queries,
    )
    return await _search_retrieval_queries(
        queries=rescue_queries,
        top_k=max(top_k, answer_top_k * 2),
        country_code=broad_country,
        deep_search=deep_search,
        provider_mode="web",
        search_settings=search_settings,
        topic_hint=topic_hint,
    )


def _evidence_rescue_enabled() -> bool:
    raw = os.getenv("EMPIRICO_ENABLE_EVIDENCE_RESCUE")
    if raw is None:
        raw = os.getenv("EMPIRICO_ENABLE_TRUSTED_GUIDELINE_RESCUE", "true")
    raw = raw.strip().lower()
    return raw not in {"0", "false", "off", "no", "none", "disabled"}


def _rescue_search_settings_for_latency_budget(
    *,
    deep_search: bool,
    latency_deadline: float | None,
) -> EvidenceRetrievalSettings | None:
    if latency_deadline is None:
        return None
    remaining = latency_deadline - time.perf_counter() - 0.75
    if remaining < _quick_rescue_min_seconds():
        return None

    settings = _search_settings_for_mode(deep_search)
    retrieval_budget = min(settings.retrieval_time_budget_seconds, remaining)
    crawl_budget = min(settings.crawl_time_budget_seconds, max(0.5, remaining - 0.25))
    request_timeout = min(
        settings.request_timeout_seconds,
        max(1, int(max(1.0, remaining))),
    )
    return settings.model_copy(
        update={
            "retrieval_time_budget_seconds": retrieval_budget,
            "crawl_time_budget_seconds": crawl_budget,
            "request_timeout_seconds": request_timeout,
        }
    )


def _quick_rescue_min_seconds() -> float:
    return _env_float(
        "EMPIRICO_QUICK_RESCUE_MIN_SECONDS",
        2.5,
        minimum=1.0,
        maximum=10.0,
    )


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


def _evidence_search_top_k(deep_search: bool) -> int:
    default = 24 if deep_search else 8
    mode_key = "EMPIRICO_DEEP_SEARCH_TOP_K" if deep_search else "EMPIRICO_QUICK_SEARCH_TOP_K"
    raw = os.getenv(mode_key) or str(default)
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, min(value, 25))


def _answer_top_k(deep_search: bool) -> int:
    default = DEFAULT_DEEP_ANSWER_SOURCES if deep_search else DEFAULT_QUICK_ANSWER_SOURCES
    key = "EMPIRICO_DEEP_ANSWER_TOP_K" if deep_search else "EMPIRICO_QUICK_ANSWER_TOP_K"
    return _env_int(key, default, minimum=default, maximum=default)


DEFAULT_QUICK_MODEL_TIMEOUT_SECONDS = 30.0
DEFAULT_DEEP_MODEL_TIMEOUT_SECONDS = 120.0


def _model_timeout_for_mode(deep_search: bool) -> float:
    """Timeout for the answer-generation call itself.

    Per-mode overrides below the safety floor are ignored: a quick answer of a
    few hundred words takes several seconds to generate, and a timeout shorter
    than that only produces failures.
    """
    key = "EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS" if deep_search else "EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS"
    minimum_timeout = 30.0 if deep_search else 8.0
    default_timeout = DEFAULT_DEEP_MODEL_TIMEOUT_SECONDS if deep_search else DEFAULT_QUICK_MODEL_TIMEOUT_SECONDS
    global_timeout = _env_float(
        "MODEL_SERVICE_TIMEOUT_SECONDS",
        180.0,
        minimum=minimum_timeout,
        maximum=300.0,
    )
    raw_mode_timeout = os.getenv(key)
    if raw_mode_timeout is None or not raw_mode_timeout.strip():
        return min(default_timeout, global_timeout)
    try:
        raw_mode_value = float(raw_mode_timeout)
    except ValueError:
        return min(default_timeout, global_timeout)
    if raw_mode_value < minimum_timeout:
        logger.warning(
            "%s=%s is below the %.0fs floor and is ignored; using %.0fs",
            key,
            raw_mode_timeout,
            minimum_timeout,
            min(default_timeout, global_timeout),
        )
        return min(default_timeout, global_timeout)
    return min(raw_mode_value, 300.0, global_timeout)


def _quick_latency_deadline(
    deep_search: bool,
    *,
    multi_branch: bool = False,
) -> float | None:
    if deep_search:
        return None
    target_seconds = _quick_latency_target_seconds()
    if multi_branch:
        target_seconds = max(target_seconds, 28.0)
    if target_seconds <= 0:
        return None
    return time.perf_counter() + target_seconds


def _quick_latency_target_seconds() -> float:
    raw = os.getenv("EMPIRICO_QUICK_LATENCY_TARGET_SECONDS")
    if raw is None or not raw.strip():
        return DEFAULT_QUICK_LATENCY_TARGET_SECONDS
    normalized = raw.strip().lower()
    if normalized in {"0", "false", "off", "no", "none", "disabled"}:
        return 0.0
    try:
        value = float(normalized)
    except ValueError:
        return DEFAULT_QUICK_LATENCY_TARGET_SECONDS
    return max(5.0, min(value, 60.0))


def _model_timeout_with_latency_deadline(
    *,
    deep_search: bool,
    latency_deadline: float | None,
    reserve_seconds: float = 0.25,
) -> float:
    timeout = _model_timeout_for_mode(deep_search)
    if latency_deadline is None:
        return timeout
    remaining = latency_deadline - time.perf_counter() - reserve_seconds
    if remaining <= 0:
        return 0.0
    return min(timeout, max(0.0, remaining))


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
            min(DEEP_SEARCH_MAX_OUTPUT_TOKENS, 5000),
            minimum=500,
            maximum=DEEP_SEARCH_MAX_OUTPUT_TOKENS,
        )
    return _env_int(
        "EMPIRICO_QUICK_MAX_OUTPUT_TOKENS",
        min(QUICK_SEARCH_MAX_OUTPUT_TOKENS, 2000),
        minimum=300,
        maximum=QUICK_SEARCH_MAX_OUTPUT_TOKENS,
    )


def _search_settings_for_mode(deep_search: bool):
    settings = get_settings()
    prefix = "EMPIRICO_DEEP" if deep_search else "EMPIRICO_QUICK"
    retrieval_default = settings.retrieval_time_budget_seconds if deep_search else min(settings.retrieval_time_budget_seconds, 10.0)
    crawl_default = settings.crawl_time_budget_seconds if deep_search else min(settings.crawl_time_budget_seconds, 8.0)
    request_timeout_default = settings.request_timeout_seconds if deep_search else min(settings.request_timeout_seconds, 12)
    crawl_sources_default = min(settings.crawl_max_sources, 8) if deep_search else min(settings.crawl_max_sources, 4)
    crawl_pages_default = min(settings.crawl_max_pages, 16) if deep_search else min(settings.crawl_max_pages, 8)
    max_results_default = min(settings.max_results_per_provider, 8) if deep_search else min(settings.max_results_per_provider, 4)
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
            reject_below=None,
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
            if _item_query_term_coverage(item, query) < 1:
                continue
            filtered.append(item)
            continue
        if query and not _item_has_query_signal(item, query):
            continue
        filtered.append(item)
    return sorted(
        filtered,
        key=lambda item: _source_priority(item, source_preference_terms, query),
    )


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
) -> tuple[int, int, int, int, int, int, int, int, int, int]:
    source = _source_key(item)
    policy_tier, type_tier = evidence_policy_sort_key(
        source=source,
        evidence_type=str(item.get("evidence_type") or ""),
        url=str(item.get("url") or item.get("full_text_url") or ""),
        text=_item_search_text(item),
    )
    direct_title_match = _item_title_url_specificity(item, query)
    direct_answer_score = _item_direct_answer_score(item, query)
    answer_specificity = _item_answer_specificity(item, query)
    return (
        0 if direct_title_match else 1,
        _source_preference_tier(item, source_preference_terms),
        policy_tier,
        _regional_source_preference_tier(item, source_preference_terms),
        -direct_title_match,
        -direct_answer_score,
        -answer_specificity,
        type_tier,
        -_item_publication_year(item),
        SOURCE_PRIORITY.get(source, 99),
    )


def _source_preference_tier(
    item: dict[str, Any],
    source_preference_terms: tuple[str, ...],
) -> int:
    if not source_preference_terms:
        return 1
    text = _item_search_text(item)
    local_terms = LOCAL_SOURCE_PREFERENCE_TERMS.intersection(source_preference_terms)
    if local_terms and any(term in text for term in local_terms):
        return 0
    return 1


def _regional_source_preference_tier(
    item: dict[str, Any],
    source_preference_terms: tuple[str, ...],
) -> int:
    if not source_preference_terms:
        return 1
    text = _item_search_text(item)
    regional_terms = REGIONAL_SOURCE_PREFERENCE_TERMS.intersection(source_preference_terms)
    if regional_terms and any(term in text for term in regional_terms):
        return 0
    return 1


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
    return sum(1 for term in query_terms if _term_matches_text_terms(term, text_terms))


def _item_direct_answer_score(item: dict[str, Any], query: str) -> int:
    query_terms = set(_snippet_focus_terms(query))
    if not query_terms:
        return 0
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    text = _compact_plain_text(
        " ".join(
            str(part)
            for part in (
                item.get("title"),
                item.get("abstract"),
                item.get("snippet"),
                raw.get("document_title"),
            )
            if part
        )
    )
    if not text:
        return 0
    return _snippet_sentence_score(text, query_terms)


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
    text_terms = set(re.findall(r"[a-z0-9]{3,}", text))
    return sum(
        1
        for term in query_terms
        if term in text or _term_matches_text_terms(term, text_terms)
    )


def _merge_evidence_items(
    primary_items: list[dict[str, Any]],
    fallback_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for item in [*primary_items, *fallback_items]:
        key = _evidence_passage_identity(item)
        if key in seen:
            existing_index = seen[key]
            if _evidence_item_merge_score(item) > _evidence_item_merge_score(merged[existing_index]):
                merged[existing_index] = item
            continue
        seen[key] = len(merged)
        merged.append(item)
    return merged


def _evidence_item_merge_score(item: dict[str, Any]) -> float:
    score = _float_or_zero(item.get("final_score"))
    return max(score, _float_or_zero(item.get("relevance_score")))


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _unique_evidence_sources(
    items: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = _evidence_source_identity(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _unique_evidence_passages(
    items: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = _evidence_passage_identity(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _evidence_passage_identity(item: dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    document_identity = _evidence_source_identity(item)
    page = _evidence_record_exact_page(item)
    locator = _normalize_search_text(
        _compact_nullable_text(
            [
                _text_from_unknown(raw.get("section_title")),
                _text_from_unknown(raw.get("section")),
                _text_from_unknown(raw.get("heading")),
                _text_from_unknown(metadata.get("section_title")),
                _text_from_unknown(item.get("section_title")),
                _text_from_unknown(item.get("section")),
                _text_from_unknown(item.get("heading")),
            ]
        )
        or ""
    )
    body = _compact_plain_text(str(item.get("abstract") or item.get("snippet") or ""))
    text_fingerprint = hashlib.sha1(
        _normalize_search_text(body[:1200]).encode()
    ).hexdigest()[:16] if body else ""
    explicit_passage = _text_from_unknown(
        _first_present(
            item,
            ("passage_id", "passageId", "chunk_id", "chunkId"),
        )
    )
    if not explicit_passage:
        explicit_passage = _text_from_unknown(
            _first_present(
                raw,
                ("passage_id", "passageId", "chunk_id", "chunkId", "doc_key"),
            )
        )
    passage_parts = [
        document_identity,
        f"passage:{_normalize_identifier_for_adapter(explicit_passage)}" if explicit_passage else "",
        f"page:{page}" if page else "",
        f"section:{locator}" if locator else "",
        f"text:{text_fingerprint}" if text_fingerprint else "",
    ]
    return "|".join(part for part in passage_parts if part) or repr(item)


def _evidence_source_identity(item: dict[str, Any]) -> str:
    doi = _text_from_unknown(item.get("doi"))
    pmid = _text_from_unknown(item.get("pmid"))
    pmcid = _text_from_unknown(item.get("pmcid"))
    if doi:
        return f"doi:{_normalize_identifier_for_adapter(doi)}"
    if pmid:
        return f"pmid:{_normalize_identifier_for_adapter(pmid)}"
    if pmcid:
        return f"pmcid:{_normalize_identifier_for_adapter(pmcid)}"

    citation = _normalize_evidence_record(item)
    url = str(
        (citation or {}).get("url")
        or item.get("url")
        or item.get("full_text_url")
        or ""
    ).strip()
    if url:
        try:
            parsed = urlparse(url)
        except ValueError:
            parsed = None
        if parsed is not None:
            query = "" if str(parsed.query).startswith("$filter=") else parsed.query
            return (
                "url:"
                f"{parsed.netloc.lower().removeprefix('www.')}"
                f"{parsed.path.rstrip('/')}?{query}"
            )

    title = _normalize_search_text(
        clean_reference_title(
            str((citation or {}).get("title") or item.get("title") or "")
        )
    )
    return f"title:{title}" if title else repr(item)


def _normalize_identifier_for_adapter(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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
    text_terms = set(re.findall(r"[a-z0-9]{3,}", text))
    return not query_terms or any(
        term in text or _term_matches_text_terms(term, text_terms)
        for term in query_terms
    )


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
    return _item_query_term_coverage_for_terms(item, _normalized_query_terms(query))


def _item_has_query_signal(item: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    if _item_title_url_specificity(item, query) >= 1:
        return True
    query_terms = _normalized_query_terms(query)
    required_coverage = _required_item_query_term_coverage(query_terms)
    if _item_query_term_coverage_for_terms(item, query_terms) < required_coverage:
        return False
    return _item_text_segment_query_term_coverage(item, query_terms) >= required_coverage


def _item_query_term_coverage_for_terms(
    item: dict[str, Any],
    query_terms: tuple[str, ...],
) -> int:
    if not query_terms:
        return 0
    text_terms = set(re.findall(r"[a-z0-9]{3,}", _item_search_text(item)))
    matched_text_terms: set[str] = set()
    for term in query_terms:
        matched = _matching_text_term(term, text_terms)
        if matched:
            matched_text_terms.add(matched)
    return len(matched_text_terms)


def _matching_text_term(term: str, text_terms: set[str]) -> str:
    if term in text_terms:
        return term
    if len(term) > 4 and term.endswith("s") and term[:-1] in text_terms:
        return term[:-1]
    for candidate in sorted(text_terms):
        if len(candidate) > 4 and candidate.endswith("s") and candidate[:-1] == term:
            return candidate
        if _tokens_share_substantial_root(term, candidate):
            return candidate
    return ""


def _required_item_query_term_coverage(query_terms: tuple[str, ...]) -> int:
    if len(query_terms) <= 2:
        return 1
    return 2


def _item_text_segment_query_term_coverage(
    item: dict[str, Any],
    query_terms: tuple[str, ...],
) -> int:
    text = _compact_plain_text(str(item.get("abstract") or item.get("snippet") or ""))
    if not text:
        return 0
    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+|\n+", text)
        if segment.strip()
    ] or [text]
    return max(
        (
            _text_query_term_coverage(segment, query_terms)
            for segment in segments
        ),
        default=0,
    )


def _text_query_term_coverage(text: str, query_terms: tuple[str, ...]) -> int:
    text_terms = set(re.findall(r"[a-z0-9]{3,}", _normalize_search_text(text)))
    matched_text_terms: set[str] = set()
    for term in query_terms:
        matched = _matching_text_term(term, text_terms)
        if matched:
            matched_text_terms.add(matched)
    return len(matched_text_terms)


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


DEFAULT_QUICK_CONTEXT_SOURCES = 12
DEFAULT_DEEP_CONTEXT_SOURCES = 20
DEFAULT_QUICK_MAX_REFERENCES = 4
DEFAULT_DEEP_MAX_REFERENCES = 8
MAX_PASSAGES_PER_DOCUMENT = 3
MMR_REDUNDANCY_WEIGHT = 0.6
MMR_POSITION_DECAY = 0.15


def _answer_candidates(
    raw_evidence: list[dict[str, Any]],
    *,
    query: str,
    source_preference_terms: tuple[str, ...],
    deep_search: bool,
    topic_hint: str = "",
) -> list[dict[str, Any]]:
    """Choose the passages the answer model reads, without a second model call.

    The model gets every plausibly relevant candidate and decides itself what to
    cite. This function only removes clear noise and orders what is left:
    source authority (national guideline > WHO/primary guidance > article
    databases), evidence type, how recent the document is, then retrieval score.
    It never ranks by whether a passage happens to mention a preferred place name.
    """
    filtered = _filter_evidence_items(
        raw_evidence,
        query=query,
        source_preference_terms=source_preference_terms,
    )
    filtered = _readmit_passages_from_relevant_documents(
        filtered,
        raw_evidence,
        query=query,
        source_preference_terms=source_preference_terms,
    )
    filtered = _keep_on_topic_passages(filtered, topic_hint)
    substantive = [item for item in filtered if _passage_is_substantive(item)]
    ordered = sorted(
        substantive or filtered,
        key=lambda item: _candidate_order_key(item, source_preference_terms),
    )

    limit = _context_sources_limit(deep_search)
    document_limit = _context_documents_limit(deep_search)

    passages_by_document: dict[str, list[dict[str, Any]]] = {}
    for item in _unique_evidence_passages(ordered, limit=len(ordered)):
        passages_by_document.setdefault(_evidence_source_identity(item), []).append(item)
    documents = list(passages_by_document)[:document_limit]

    # Breadth first: the best passage of each document, so no single document can
    # spend every slot. Then depth: further passages chosen to complement what is
    # already selected, which is what keeps a triage or decision page alongside
    # the dosing page of the same guideline.
    selected: list[dict[str, Any]] = []
    for document in documents:
        if len(selected) >= limit:
            break
        selected.append(passages_by_document[document][0])

    for depth in range(1, MAX_PASSAGES_PER_DOCUMENT):
        for document in documents:
            if len(selected) >= limit:
                return selected
            complementary = _complementary_passage(
                passages_by_document[document][1:],
                selected,
            )
            if complementary is not None:
                selected.append(complementary)
    return selected


def _complementary_passage(
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Highest-ranked candidate that adds most to what is already selected.

    Maximal marginal relevance: rank position minus overlap with the passages
    already chosen. Without it the top passages of a long guideline are often
    near-neighbours of one another and the answer inherits their single
    viewpoint, for example three pages of dosing detail and no triage criteria.
    """
    remaining = [item for item in candidates if id(item) not in {id(chosen) for chosen in selected}]
    if not remaining:
        return None
    selected_tokens = [_passage_tokens(item) for item in selected]
    best_item: dict[str, Any] | None = None
    best_score = float("-inf")
    for position, item in enumerate(remaining):
        # Gentle positional decay: rank still leads, but a genuinely new angle a
        # few places down can outrank a paraphrase of what is already selected.
        relevance = max(0.0, 1.0 - (MMR_POSITION_DECAY * position))
        tokens = _passage_tokens(item)
        redundancy = max(
            (_token_set_similarity(tokens, other) for other in selected_tokens),
            default=0.0,
        )
        score = relevance - (MMR_REDUNDANCY_WEIGHT * redundancy)
        if score > best_score:
            best_score = score
            best_item = item
    return best_item


def _passage_tokens(item: dict[str, Any]) -> frozenset[str]:
    text = str(item.get("abstract") or item.get("snippet") or item.get("title") or "")
    return frozenset(
        token
        for token in re.findall(r"[a-z0-9]{4,}", text.lower())
        if token not in QUERY_TERM_STOPWORDS
    )


def _token_set_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    if not intersection:
        return 0.0
    return intersection / len(left | right)


MIN_PASSAGE_WORDS = 4
MIN_PASSAGE_WORD_RATIO = 0.45
MIN_EXEMPT_SPECIFICITY = 0.4


def _passage_is_substantive(item: dict[str, Any]) -> bool:
    """Whether a passage states something, rather than labelling or tabulating it.

    Crawled documents yield cover pages, running heads, and tables of figures
    that match a query lexically but assert nothing. They are indistinguishable
    from real content by source or score, and each one costs a slot the model
    could have spent on a recommendation.

    The test is shape, not length: a title has no sentence, a table of figures is
    mostly numerals, while a triage rule such as "admit if complications, treat
    at home if appetite is intact" is short, qualitative and exactly what a
    length threshold would have thrown away.
    """
    text = _compact_plain_text(str(item.get("abstract") or item.get("snippet") or ""))
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]{2,}\b", text)
    if len(words) < MIN_PASSAGE_WORDS:
        return False
    tokens = re.findall(r"\S+", text)
    if (len(words) / max(len(tokens), 1)) < MIN_PASSAGE_WORD_RATIO:
        return False
    if clinical_specificity_score(text) >= MIN_EXEMPT_SPECIFICITY:
        return True
    return bool(re.search(r"[.!?](?:\s|$)", text) or re.search(r"(?:^|\s)[-•*\u2022]\s", text))


def _keep_on_topic_passages(
    items: list[dict[str, Any]],
    topic_hint: str,
) -> list[dict[str, Any]]:
    """Drop passages that do not mention what the question is about.

    Per-passage relevance is otherwise judged on any two words of the question,
    and words like "treatment" or "adult" appear in every clinical document, so
    a guideline on another condition passes. The subject identified upstream is
    the one term that must actually be present. Falls back to the unfiltered set
    Returning nothing is valid: it triggers the mandatory retry,
    which searches wider. Keeping off-topic passages so the answer has something
    to cite is how otitis media guidance gets cited for septic shock.
    """
    topic_terms = _normalized_query_terms(topic_hint) if topic_hint else ()
    if not topic_terms or not items:
        return items
    # One shared word is not a topic: "acute otitis media" and "severe acute
    # malnutrition" meet only at "acute". A subject named in several words has
    # to be matched by several, the same bar source selection uses.
    required = 2 if len(topic_terms) > 1 else 1
    return [
        item
        for item in items
        if _item_query_term_coverage_for_terms(item, topic_terms) >= required
    ]


def _readmit_passages_from_relevant_documents(
    accepted: list[dict[str, Any]],
    raw_evidence: list[dict[str, Any]],
    *,
    query: str,
    source_preference_terms: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Let other passages of an already-relevant document back into the pool.

    Relevance is judged per passage on the words it repeats, but the page of a
    guideline that carries the dose often does not repeat the condition name;
    the chapter heading did that. Re-admission needs the question to name the
    document, through its title or URL, rather than merely one passage matching:
    without that a guideline on another disease pulls its whole contents in on
    the strength of a single incidental mention. Structural exclusions still
    apply, since this passes an empty query and skips only the query checks.
    """
    if not accepted:
        return accepted
    relevant_documents = {
        _evidence_source_identity(item)
        for item in accepted
        if _item_title_url_specificity(item, query) >= 1
    }
    if not relevant_documents:
        return accepted
    structurally_valid = _filter_evidence_items(
        raw_evidence,
        query="",
        source_preference_terms=source_preference_terms,
    )
    siblings = [
        item
        for item in structurally_valid
        if _evidence_source_identity(item) in relevant_documents
    ]
    return _merge_evidence_items(accepted, siblings)


def _candidate_order_key(
    item: dict[str, Any],
    source_preference_terms: tuple[str, ...] = (),
) -> tuple[int, int, float, int, int, float]:
    """Order candidates by usefulness, then jurisdiction, then recency.

    The sequence matters and each step earns its place:

    1. Source authority, so guidance outranks an article database.
    2. Evidence type, so a guideline outranks a review.
    3. Whether the passage states doses, thresholds or durations. An older
       document that gives the regimen beats a newer page that only names it.
    4. Jurisdiction: between two equally useful passages the local one wins,
       even when the other is newer, which is what a clinician here wants.
    5. Recency, which then decides between editions of comparable guidance.
    6. Retrieval score.
    """
    policy_tier, type_tier = evidence_policy_sort_key(
        source=_source_key(item),
        evidence_type=str(item.get("evidence_type") or ""),
        url=str(item.get("url") or item.get("full_text_url") or ""),
        text=_item_search_text(item),
    )
    return (
        policy_tier,
        type_tier,
        -_candidate_specificity(item),
        _jurisdiction_band(item, source_preference_terms),
        _recency_band(item),
        -_float_or_zero(item.get("final_score")),
    )


def _jurisdiction_band(
    item: dict[str, Any],
    source_preference_terms: tuple[str, ...],
) -> int:
    """0 when the document itself belongs to the preferred jurisdiction.

    Matched against the document's identity only, never its body text. A study
    that merely mentions Kampala is not Ugandan guidance, while a national
    manual is, whatever server happens to host the PDF.
    """
    if not source_preference_terms:
        return 1
    local_terms = LOCAL_SOURCE_PREFERENCE_TERMS.intersection(source_preference_terms)
    if not local_terms:
        return 1
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    identity = _normalize_search_text(
        " ".join(
            str(part)
            for part in (
                item.get("title"),
                item.get("journal_or_publisher"),
                item.get("url"),
                item.get("full_text_url"),
                raw.get("document_title"),
                raw.get("publisher"),
                raw.get("source_name"),
                raw.get("source_url"),
            )
            if part
        )
    )
    return 0 if any(term in identity for term in local_terms) else 1


def _candidate_specificity(item: dict[str, Any]) -> float:
    """Coarse actionability of a passage, used only to break ranking ties.

    Rounded hard so that it separates a passage naming doses or thresholds from
    one that only names a care pathway, without letting a small difference
    outrank the retrieval score.
    """
    text = str(item.get("abstract") or item.get("snippet") or "")
    return round(clinical_specificity_score(text), 1)


def _recency_band(item: dict[str, Any]) -> int:
    """Coarse age band of a document, lower being more recent.

    Guidance is superseded by newer editions, so within one authority tier the
    current edition should reach the model first. The bands are wide so that a
    small difference in year never outranks relevance, and an undated document
    sits in the middle rather than last: most crawled guideline pages carry no
    machine-readable date and must not be pushed below a decade-old PDF.
    """
    year = _document_year(item)
    if year <= 0:
        return 2
    age = _current_year() - year
    if age <= 3:
        return 0
    if age <= 8:
        return 1
    if age <= 15:
        return 3
    return 4


def _document_year(item: dict[str, Any]) -> int:
    """Publication year from metadata, else the latest year named in the title or URL."""
    year = _item_publication_year(item)
    if year:
        return year
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    text = " ".join(
        str(part)
        for part in (
            item.get("title"),
            raw.get("document_title"),
            _url_without_fragment(str(item.get("url") or item.get("full_text_url") or "")),
        )
        if part
    )
    return _latest_year_in_text(text)


def _latest_year_in_text(text: str) -> int:
    maximum = _current_year() + 1
    years = [
        value
        for value in (int(match) for match in re.findall(r"(?<!\d)(19[89]\d|20\d{2})(?!\d)", text))
        if 1980 <= value <= maximum
    ]
    return max(years) if years else 0


def _url_without_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def _current_year() -> int:
    return time.gmtime().tm_year


def _context_sources_limit(deep_search: bool) -> int:
    """Maximum passages offered to the answer model."""
    key = "EMPIRICO_DEEP_CONTEXT_SOURCES" if deep_search else "EMPIRICO_QUICK_CONTEXT_SOURCES"
    default = DEFAULT_DEEP_CONTEXT_SOURCES if deep_search else DEFAULT_QUICK_CONTEXT_SOURCES
    return _env_int(key, default, minimum=3, maximum=40)


def _max_references(deep_search: bool) -> int:
    """Maximum distinct documents cited in the final answer."""
    key = "EMPIRICO_DEEP_MAX_REFERENCES" if deep_search else "EMPIRICO_QUICK_MAX_REFERENCES"
    default = DEFAULT_DEEP_MAX_REFERENCES if deep_search else DEFAULT_QUICK_MAX_REFERENCES
    return _env_int(key, default, minimum=1, maximum=20)


def _context_documents_limit(deep_search: bool) -> int:
    """Distinct documents offered to the model: a little more than it may cite."""
    return _max_references(deep_search) + 2


def _normalize_evidence_record(record: dict[str, Any]) -> dict[str, object] | None:
    url = _source_url_from_record(record)
    if not url:
        return None

    page = _evidence_record_exact_page(record) or _exact_page_from_url(url)
    if page is not None:
        page_url = _source_url_with_exact_page(url, page)
    else:
        page_url = _source_url_with_text_fragment(
            url,
            _evidence_record_exact_text_fragment(record),
            record,
        )
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
                    "landing_page_url",
                    "landingPageUrl",
                    "open_url",
                    "openUrl",
                    "pdf_url",
                    "pdfUrl",
                    "download_url",
                    "downloadUrl",
                    "source_public_url",
                    "sourcePublicUrl",
                    "external_url",
                    "externalUrl",
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
    for key in ("id", "identifier", "source_id", "sourceId"):
        url = _url_from_text(_text_from_unknown(record.get(key)) or "")
        if url:
            return url
    return None


def _url_from_text(value: str) -> str | None:
    match = re.search(r"https?://[^\s<>)\]]+", value)
    if not match:
        return None
    return _clean_source_url(match.group(0))


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
    parsed = urlparse(url)
    fragment = f"page={page}"
    return parsed._replace(fragment=fragment).geturl()


def _source_url_with_text_fragment(url: str, text: str | None, record: dict[str, Any]) -> str:
    if not text or _is_pdf_like_reference_url(url):
        return url
    if not _record_supports_text_fragment(record):
        return url
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if parsed.fragment:
        return url
    fragment = _text_fragment_from_evidence_text(text)
    if not fragment:
        return url
    return parsed._replace(fragment=f":~:text={quote(fragment, safe='')}").geturl()


def _record_supports_text_fragment(record: dict[str, Any]) -> bool:
    if _source_key(record) != "crawl4ai":
        return False
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    retrieval_mode = str(raw.get("retrieval_mode") or "").strip().lower()
    return retrieval_mode in {"browser", "static_html", "static_html_cache"}


def _is_pdf_like_reference_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    path = parsed.path.lower()
    return bool(
        path.endswith(".pdf")
        or "/bitstream/" in path
        or "/bitstreams/" in path
        or path.endswith("/content")
    )


def _text_fragment_from_evidence_text(text: str) -> str | None:
    cleaned = re.sub(r"(?:https?://|www\.)\S+", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[[0-9,\s]+\]", " ", cleaned)
    cleaned = _compact_plain_text(cleaned)
    if not cleaned:
        return None
    candidates = [
        sentence.strip(" .;:,")
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if 24 <= len(sentence.strip()) <= 180
    ]
    if not candidates:
        candidates = [cleaned[:160].strip(" .;:,")]
    fragment = candidates[0]
    fragment = re.sub(r"\s+", " ", fragment).strip(" .;:,")
    if len(fragment) < 20:
        return None
    return fragment[:120].rstrip(" ,;:")


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
                "source_name",
                "sourceName",
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


def _evidence_record_exact_text_fragment(record: dict[str, Any]) -> str | None:
    for text in _evidence_record_body_text_candidates(record):
        if _text_fragment_from_evidence_text(text):
            return text
    locator = _evidence_record_locator(record)
    if locator and _text_fragment_from_evidence_text(locator):
        return locator
    return None


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
                nested.get("source_name"),
                nested.get("sourceName"),
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


def _bool_from_unknown(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "pass", "passed"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "fail", "failed"}:
            return False
    return default


def _compact_nullable_text(parts: list[str | None]) -> str | None:
    text = _compact_plain_text(" ".join(part for part in parts if part))
    return text or None


def _compact_plain_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _text_contains_inline_enumeration(text: str) -> bool:
    markers = [int(match.group(1)) for match in re.finditer(r"(?:^|\s)(\d{1,2})[\).]\s+\S+", text)]
    return any(current == previous + 1 for previous, current in zip(markers, markers[1:]))


def _no_retrieved_evidence_answer() -> str:
    return (
        "I do not have usable retrieved reference text for this request, so I cannot provide "
        "a referenced recommendation safely. Please verify the answer against the latest "
        "relevant clinical guideline, local protocol, or a senior clinician before applying it."
    )


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


_RAW_URL_PATTERN = (
    r"(?:https?://|www\.)[^\s<>)\]]+"
    r"|(?:[a-z0-9-]+\.)+(?:gov|int|org|edu|com|net|ug|uk|io|ai)"
    r"(?:/[^\s<>)\]]*)?"
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

    segments = _snippet_candidate_segments(compact)
    if len(segments) <= 1:
        return _compact_text(compact, max_length)

    scored: list[tuple[int, int, str]] = []
    for index, segment in enumerate(segments):
        score = _snippet_sentence_score(segment, query_terms)
        if score > 0:
            scored.append((score, index, segment))

    if not scored:
        return _compact_text(compact, max_length)

    segment_limit = 1 if re.search(r"\s+\.\.\.\s+", compact) else 3
    selected_indexes = sorted(
        index
        for _score, index, _sentence in sorted(scored, reverse=True)[:segment_limit]
    )
    selected: list[str] = []
    current_length = 0
    for index in selected_indexes:
        segment = segments[index]
        projected = current_length + len(segment) + (1 if selected else 0)
        if selected and projected > max_length:
            break
        selected.append(segment)
        current_length = projected
    return _compact_text(" ".join(selected) or compact, max_length)


def _snippet_candidate_segments(compact: str) -> list[str]:
    ellipsis_segments = [
        segment.strip()
        for segment in re.split(r"\s+\.\.\.\s+", compact)
        if segment.strip()
    ]
    if len(ellipsis_segments) > 1:
        return ellipsis_segments
    if _text_contains_inline_enumeration(compact):
        return [compact]
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if sentence.strip()
    ]


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
    for candidate in text_terms:
        if len(candidate) > 4 and candidate.endswith("s") and candidate[:-1] == term:
            return True
        if _tokens_share_substantial_root(term, candidate):
            return True
    return False


def _tokens_share_substantial_root(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 8:
        return False
    longest = _longest_common_substring_length(left, right)
    return longest >= max(7, int(min(len(left), len(right)) * 0.7))


def _longest_common_substring_length(left: str, right: str) -> int:
    previous = [0] * (len(right) + 1)
    best = 0
    for left_char in left:
        current = [0] * (len(right) + 1)
        for index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                current[index] = previous[index - 1] + 1
                best = max(best, current[index])
        previous = current
    return best


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
    provider_mode: str | None = None,
    search_settings: EvidenceRetrievalSettings | None = None,
    topic_hint: str | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _run_local_evidence_search,
        query,
        top_k,
        country_code,
        provider_mode or _local_evidence_provider_mode(deep_search),
        deep_search,
        search_settings,
        topic_hint,
    )


def _run_local_evidence_search(
    query: str,
    top_k: int,
    country_code: Optional[str],
    provider_mode: str,
    deep_search: bool,
    search_settings: EvidenceRetrievalSettings | None = None,
    topic_hint: str | None = None,
) -> dict[str, Any]:
    effective_country_code = None if (country_code or "").upper() == "GLOBAL" else country_code
    try:
        result = EvidenceSearchService(
            settings=search_settings or _search_settings_for_mode(deep_search),
            country_code=effective_country_code,
            provider_mode=provider_mode,
            topic_hint=topic_hint,
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
        return "UG"
    return raw.upper()


def _country_code_for_retrieval_query(
    default_country_code: Optional[str],
    retrieval_query: str,
) -> Optional[str]:
    if (default_country_code or "").upper() == "GLOBAL":
        return "GLOBAL"
    explicit = _explicit_country_code_from_text(retrieval_query)
    return explicit or default_country_code


def _explicit_country_code_from_text(text: str) -> Optional[str]:
    normalized = _normalize_search_text(text)
    country_terms = {
        "UG": ("uganda", "ugandan", "health.go.ug", "library.health.go.ug"),
        "KE": ("kenya", "kenyan", "health.go.ke"),
        "TZ": ("tanzania", "tanzanian", "moh.go.tz", "nmcp.go.tz"),
    }
    matches = [
        code
        for code, terms in country_terms.items()
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized)
            for term in terms
        )
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _broad_evidence_country_code(country_code: Optional[str]) -> str:
    return "GLOBAL" if (country_code or "").upper() != "GLOBAL" else "GLOBAL"


def _local_evidence_provider_mode(deep_search: bool) -> str:
    mode_key = (
        "EMPIRICO_DEEP_EVIDENCE_PROVIDER_MODE"
        if deep_search
        else "EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE"
    )
    # Both modes query every provider. The providers run concurrently behind one
    # retrieval budget, so adding the article databases to quick search costs no
    # wall-clock time, and it removes the failure where a slow or unlucky crawl
    # left an answer with no references at all. Ranking, not availability, is
    # what keeps guidance above article databases.
    default = "web"
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
    if not source_preference_terms:
        return ()
    if _query_mentions_alternate_jurisdiction(query_context):
        return ()
    return source_preference_terms


def _query_mentions_alternate_jurisdiction(query_context: str) -> bool:
    text = _normalize_search_text(query_context)
    if not text:
        return False
    if _query_mentions_source_preference(text, tuple(LOCAL_SOURCE_PREFERENCE_TERMS)):
        return False
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        for term in ALTERNATE_JURISDICTION_TERMS
    )


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
