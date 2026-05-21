"""
Temporary adapter for testing live evidence retrieval through the existing chat UI.

This deliberately bypasses the current Zilliz/Milvus knowledge-base retrieval path
when EVIDENCE_RETRIEVAL_TEST_MODE is enabled. Keep this file small and easy to
remove once the experiment is folded into the production RAG architecture.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from google.api_core import exceptions
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from healthnavi.core.constants import (
    BOLDING_RULES,
    DEEP_SEARCH_PROMPT,
    DEEP_SEARCH_MAX_OUTPUT_TOKENS,
    EXAM_HANDLING,
    GLOBAL_CONDUCT_RULES,
    MODEL_NAME,
    PHARMACOLOGY_RULES,
    PREEMPTIVE_REASONING_RULES,
    QUERY_CLASSIFICATION_RULES,
    QUICK_SEARCH_PROMPT,
    QUICK_SEARCH_MAX_OUTPUT_TOKENS,
    RETRY_MAX_WAIT,
    RETRY_MIN_WAIT,
    RETRY_MULTIPLIER,
    ROLE_INSTRUCTIONS,
    SECURITY_AND_EVIDENCE_RULES,
)
from healthnavi.services.genai_client import get_genai_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = next(
    (
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "evidence_retrieval_test").exists()
    ),
    Path("/"),
)
EVIDENCE_MODULE_DIR = PROJECT_ROOT / "evidence_retrieval_test"
EVIDENCE_ENV_PATH = EVIDENCE_MODULE_DIR / ".env"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(EVIDENCE_ENV_PATH)

from evidence_retrieval_test.src.services.citation_formatter import (  # noqa: E402
    build_llm_context,
    format_citations,
)
from evidence_retrieval_test.src.services.evidence_search_service import (  # noqa: E402
    EvidenceSearchService,
)


def evidence_retrieval_test_mode_enabled() -> bool:
    """
    Default ON for this experiment so the existing UI immediately exercises the
    new provider layer. Set EVIDENCE_RETRIEVAL_TEST_MODE=false to return to the
    original Zilliz-backed flow.
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
    user_role_from_db: str | None = None,
) -> tuple[str, bool, str, list[str]]:
    total_started_at = time.perf_counter()
    top_k = 10 if deep_search else 6
    retrieval_started_at = time.perf_counter()
    result = await asyncio.to_thread(
        EvidenceSearchService().search,
        query,
        top_k,
    )
    retrieval_ms = round((time.perf_counter() - retrieval_started_at) * 1000, 1)
    source_counts = Counter(getattr(item.source, "value", str(item.source)) for item in result.items)
    logger.info(
        "Evidence retrieval test search timings: total=%.1f ms provider_timings=%s source_counts=%s errors=%d",
        retrieval_ms,
        result.timings_ms,
        dict(source_counts),
        len(result.provider_errors),
    )
    if result.provider_errors:
        logger.warning(
            "Evidence retrieval test provider warnings: %s",
            result.provider_errors,
        )

    citations = format_citations(result.items)
    llm_context = build_llm_context(result.items)
    citation_reference_block = _citation_reference_block(citations)

    if not result.items:
        return (
            "I could not retrieve enough verified evidence sources for this question. "
            "Please try rephrasing it or adding key context such as country, age, condition, or treatment setting.",
            True,
            "evidence_retrieval_test",
            [],
        )

    prompt = _build_live_evidence_prompt(
        query=query,
        patient_data=patient_data,
        chat_history=chat_history,
        llm_context=llm_context,
        citation_reference_block=citation_reference_block,
        deep_search=deep_search,
        user_role_from_db=user_role_from_db,
    )

    client = get_genai_client()

    try:
        generation_started_at = time.perf_counter()
        response = _generate_content_with_retry(
            client,
            MODEL_NAME,
            [{"role": "user", "parts": [{"text": prompt}]}],
            {
                "temperature": 0.15,
                "max_output_tokens": (
                    min(DEEP_SEARCH_MAX_OUTPUT_TOKENS, 4500)
                    if deep_search
                    else min(QUICK_SEARCH_MAX_OUTPUT_TOKENS, 3000)
                ),
                "top_p": 0.9,
                "top_k": 20,
                "candidate_count": 1,
            },
        )
        generation_ms = round((time.perf_counter() - generation_started_at) * 1000, 1)
        logger.info(
            "Evidence retrieval test generation timings: model=%.1f ms total=%.1f ms",
            generation_ms,
            (time.perf_counter() - total_started_at) * 1000,
        )
    except Exception as exc:
        logger.error("Evidence retrieval test generation failed: %s", exc, exc_info=True)
        if _is_retryable_genai_error(exc):
            return (
                "The model service is temporarily busy. The evidence retrieval completed, but answer generation failed. Please try again.",
                False,
                "evidence_retrieval_test",
                [],
            )
        return (
            user_friendly_genai_error(exc),
            False,
            "evidence_retrieval_test",
            [],
        )

    answer = _extract_text(response)
    if not answer:
        return (
            "The model returned no usable answer from the retrieved evidence. Please try a narrower query.",
            False,
            "evidence_retrieval_test",
            [],
        )

    answer = _ensure_reference_urls(answer, citations)
    logger.info(
        "Evidence retrieval test completed timings: retrieval=%.1f ms model=%.1f ms total=%.1f ms",
        retrieval_ms,
        generation_ms,
        (time.perf_counter() - total_started_at) * 1000,
    )
    return answer, True, "evidence_retrieval_test", []


def _build_live_evidence_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    llm_context: str,
    citation_reference_block: str,
    deep_search: bool,
    user_role_from_db: str | None,
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


def _role_instruction(user_role_from_db: str | None) -> str:
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


def _is_retryable_genai_error(exception: BaseException) -> bool:
    if isinstance(exception, exceptions.ResourceExhausted):
        return True
    if isinstance(exception, (exceptions.ServiceUnavailable, exceptions.InternalServerError)):
        return True
    msg = str(exception).upper()
    return (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "503" in msg
        or "UNAVAILABLE" in msg
        or "TOO_MANY_REQUESTS" in msg
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(
        multiplier=RETRY_MULTIPLIER,
        min=RETRY_MIN_WAIT,
        max=RETRY_MAX_WAIT,
    ),
    retry=retry_if_exception(_is_retryable_genai_error),
    reraise=True,
)
def _generate_content_with_retry(client, model: str, contents, config: dict):
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


def user_friendly_genai_error(exception: BaseException) -> str:
    msg = str(exception)
    upper = msg.upper()
    if "RESOURCE_EXHAUSTED" in upper or "429" in upper or "RATE" in upper:
        return "Empirico is temporarily busy. Please wait a moment and try again."
    if "SAFETY" in upper or "BLOCKED" in upper:
        return "Empirico could not complete this request. Try rephrasing your question."
    if len(msg) > 280 or "{" in msg or "googleapis" in msg.lower():
        return "Something went wrong while generating a response. Please try again in a moment."
    return "Something went wrong while generating a response. Please try again in a moment."


def _extract_text(response) -> str:
    if response and hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if (
            hasattr(candidate, "content")
            and hasattr(candidate.content, "parts")
            and candidate.content.parts
            and hasattr(candidate.content.parts[0], "text")
        ):
            return candidate.content.parts[0].text.strip()
    return ""


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
    """
    The prompt asks Gemini to include references, but for frontend testing we enforce
    a canonical one-reference-per-line block using the exact retrieved URLs.
    """
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
