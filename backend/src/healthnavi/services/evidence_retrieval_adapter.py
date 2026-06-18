"""
Adapter for routing the live-evidence experiment through the standalone model
service.

The chat service still calls this adapter exactly as before. The implementation
now delegates to the local/hosted Empirico Model Service over HTTP instead of
importing the copied evidence_retrieval_test package.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

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

logger = logging.getLogger(__name__)


def evidence_retrieval_test_mode_enabled() -> bool:
    """
    Default ON for this experiment so the existing UI immediately exercises the
    model-service endpoint. Set EVIDENCE_RETRIEVAL_TEST_MODE=false to return to
    the original Zilliz-backed flow.
    """
    return os.getenv("EVIDENCE_RETRIEVAL_TEST_MODE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def generate_evidence_retrieval_test_response(
    query: str,
    chat_history: str,
    patient_data: str,
    deep_search: bool = False,
    user_role_from_db: Optional[str] = None,
) -> tuple[str, bool, str, list[str]]:
    top_k = 10 if deep_search else 6
    prompt_type = "deep_search" if deep_search else "quick_search"

    try:
        evidence_data = await _post_evidence_search({"question": query, "top_k": top_k})
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Model service evidence search returned %s from %s: %s",
            exc.response.status_code,
            exc.request.url,
            _safe_response_text(exc.response),
        )
        return (
            "The model service is temporarily unavailable. Please try again.",
            False,
            prompt_type,
            [],
        )
    except httpx.RequestError as exc:
        logger.error("Model service evidence search failed: %s", exc, exc_info=True)
        return (
            "The model service is still starting up or cannot be reached. Please try again in a moment.",
            False,
            prompt_type,
            [],
        )
    except ValueError as exc:
        logger.error("Model service evidence search returned invalid JSON: %s", exc, exc_info=True)
        return (
            "The model service returned an invalid evidence response. Please try again.",
            False,
            prompt_type,
            [],
        )

    citations = list(evidence_data.get("citations") or [])
    llm_context = str(evidence_data.get("llm_context") or "")
    provider_errors = list(evidence_data.get("provider_errors") or [])

    if not evidence_data.get("items"):
        return (
            "I could not retrieve enough verified evidence sources for this question. "
            "Please try rephrasing it or adding key context such as country, age, condition, or treatment setting.",
            True,
            prompt_type,
            [],
        )

    prompt = _build_live_evidence_prompt(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        llm_context=llm_context,
        citation_reference_block=_citation_reference_block(citations),
        deep_search=deep_search,
        user_role_from_db=user_role_from_db,
    )
    payload = {
        "prompt": prompt,
        "prompt_type": prompt_type,
        "temperature": 0.15,
        "max_output_tokens": (
            min(DEEP_SEARCH_MAX_OUTPUT_TOKENS, 4500)
            if deep_search
            else min(QUICK_SEARCH_MAX_OUTPUT_TOKENS, 3000)
        ),
        "top_p": 0.9,
        "top_k": 20,
        "candidate_count": 1,
    }

    try:
        data = await _post_model_response(payload)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Model service returned %s from %s: %s",
            exc.response.status_code,
            exc.request.url,
            _safe_response_text(exc.response),
        )
        return (
            "The model service is temporarily unavailable. Please try again.",
            False,
            prompt_type,
            [],
        )
    except httpx.RequestError as exc:
        logger.error("Model service request failed: %s", exc, exc_info=True)
        return (
            "The model service is still starting up or cannot be reached. Please try again in a moment.",
            False,
            prompt_type,
            [],
        )
    except ValueError as exc:
        logger.error("Model service returned invalid JSON: %s", exc, exc_info=True)
        return (
            "The model service returned an invalid response. Please try again.",
            False,
            prompt_type,
            [],
        )

    answer = str(data.get("answer") or "").strip()
    if not answer:
        return (
            "The model returned no usable answer. Please try a narrower query.",
            False,
            prompt_type,
            [],
        )
    answer = _ensure_reference_urls(answer, citations)

    logger.info(
        "Model service response completed: model=%s citations=%d provider_errors=%d timings=%s",
        data.get("model"),
        len(citations),
        len(provider_errors),
        data.get("timings_ms") or {},
    )

    return (
        answer,
        bool(data.get("diagnosis_complete", True)),
        str(data.get("prompt_type") or prompt_type),
        [],
    )


async def _post_evidence_search(payload: dict[str, Any]) -> dict[str, Any]:
    base_url = _model_service_base_url()
    timeout = float(os.getenv("MODEL_SERVICE_TIMEOUT_SECONDS", "120"))
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("MODEL_SERVICE_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/v1/evidence/search",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def _build_live_evidence_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    llm_context: str,
    citation_reference_block: str,
    deep_search: bool,
    user_role_from_db: Optional[str],
) -> str:
    prompt_template = DEEP_SEARCH_PROMPT if deep_search else QUICK_SEARCH_PROMPT
    prompt = prompt_template.format(
        sources=citation_reference_block,
        context=llm_context,
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
"""
    return f"{prompt}\n\n{user_context_block.strip()}"


def _live_global_conduct_rules() -> str:
    return GLOBAL_CONDUCT_RULES.replace(
        "- No inline citations in body paragraphs.",
        "- Cite clinically important claims inline with clickable markdown markers like [1](https://source-url).",
    )


def _live_references_rules() -> str:
    return """
### REFERENCES ###
End with:
**References**

Rules:
- List only sources actually used and grounded in the EVIDENCE BASE / AVAILABLE SOURCES.
- One source per bullet.
- Use the exact clickable source URLs from AVAILABLE SOURCES.
- Format: * [1] Source title - full URL
- Do not invent page numbers, publications, URLs, PMIDs, PMCIDs, DOIs, or guideline titles.
- If multiple editions of the same guideline or source series appear in the evidence, cite the **most recent** edition that supports the recommendation.
""".strip()


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


def _citation_reference_block(citations: list[dict[str, object]]) -> str:
    if not citations:
        return "No citations retrieved."
    lines = []
    for index, citation in enumerate(citations, start=1):
        lines.append(
            f"[{index}]({citation.get('url')}) {citation.get('title')} | {citation.get('source_label')} | "
            f"{citation.get('journal') or 'n/a'} | {citation.get('year') or 'n.d.'} | "
            f"{citation.get('url')} | DOI: {citation.get('doi') or 'n/a'} | "
            f"Why relevant: {citation.get('why_relevant')}"
        )
    return "\n".join(lines)


def _ensure_reference_urls(answer: str, citations: list[dict[str, object]]) -> str:
    if not citations:
        return answer
    answer = _link_inline_citation_markers(answer, citations)
    answer_without_references = re.split(
        r"\n\s*(?:\*\*)?References(?:\*\*)?\s*\n",
        answer,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].rstrip()

    lines = ["", "", "**References**", ""]
    for index, citation in enumerate(citations, start=1):
        title = citation.get("title")
        url = citation.get("url")
        source = citation.get("source_label")
        year = citation.get("year") or "n.d."
        lines.append(f"- [{index}] [{title}]({url}) ({source}, {year})")
    return answer_without_references + "\n".join(lines)


def _link_inline_citation_markers(answer: str, citations: list[dict[str, object]]) -> str:
    citation_urls = {
        str(index): str(citation.get("url") or "")
        for index, citation in enumerate(citations, start=1)
        if citation.get("url")
    }

    def replace_double(match: re.Match[str]) -> str:
        number = match.group(1)
        url = citation_urls.get(number)
        return f"[{number}]({url})" if url else match.group(0)

    def replace_plain(match: re.Match[str]) -> str:
        number = match.group(1)
        url = citation_urls.get(number)
        return f"[{number}]({url})" if url else match.group(0)

    linked = answer
    linked = re.sub(r"\[\[(\d+)\]\](?!\()", replace_double, linked)
    linked = re.sub(r"(?<!\[)\[(\d+)\](?![\]\(])", replace_plain, linked)
    return linked


async def _post_model_response(payload: dict[str, Any]) -> dict[str, Any]:
    base_url = _model_service_base_url()
    timeout = float(os.getenv("MODEL_SERVICE_TIMEOUT_SECONDS", "120"))
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("MODEL_SERVICE_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/v1/model/respond",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def _model_service_base_url() -> str:
    return (
        os.getenv("MODEL_SERVICE_BASE_URL")
        or os.getenv("EMPIRICO_MODEL_SERVICE_URL")
        or "http://127.0.0.1:8080"
    ).rstrip("/")


def _safe_response_text(response: httpx.Response) -> str:
    text = response.text.strip()
    if len(text) > 500:
        return text[:500] + "..."
    return text
