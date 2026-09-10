"""
Answer composition for Empirico.

Two responsibilities, both deterministic:

1. ``build_answer_prompt`` assembles the single generation prompt sent to the
   shared Empirico Model Service: identity and style instructions, the user's
   question and conversation, and the numbered evidence sources.
2. ``finalize_answer`` turns the model's answer into the display contract the
   web and mobile clients render: inline ``[n](url)`` citation links that are
   renumbered in order of first use, followed by a ``**References**`` list
   built from the retrieved source metadata.

This module never rewrites the model's prose. If the answer is poor, fix the
prompt, the evidence, or the model settings, not the text after the fact.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

from healthnavi.core.constants import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_BLOCK,
    DEEP_DEPTH_RULE,
    DEFAULT_JURISDICTION_RULE,
    EXAM_HANDLING,
    NO_SOURCES_RULE,
    QUICK_DEPTH_RULE,
    ROLE_INSTRUCTIONS,
)

EXAM_ROLES = {"TRAINEE", "STUDENT"}

_ROLE_KEY_BY_PROFESSION = {
    "Consultant": "EXPERT",
    "Specialist": "EXPERT",
    "Senior House Officer": "CLINICIAN",
    "Senior House Officers": "CLINICIAN",
    "Medical Officer": "CLINICIAN",
    "Clinical Officer": "CLINICIAN",
    "Other Clinical Practitioner": "CLINICIAN",
    "Intern Clinician": "TRAINEE",
    "Intern Doctor": "TRAINEE",
    "Clinical/Medical Student": "STUDENT",
    "Student": "STUDENT",
}

# A References/Sources heading the model may have written despite instructions.
_REFERENCES_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*|\*\*|__)?\s*(?:references?|sources?|bibliography)\s*:?\s*(?:\*\*|__)?\s*:?\s*$",
    re.IGNORECASE,
)
# [1], [1, 2], [1,2,3] optionally followed by a markdown link target the model added.
_MARKER = re.compile(r"(?<!\[)\[(\d{1,3}(?:\s*[,\-\u2013]\s*\d{1,3})*)\](?:\([^)\s]*\))?")
# A run of adjacent markers ("[1][2]", "[1] [3](url)") is relinked as one unit so
# markers that resolve to the same source collapse into a single link.
_MARKER_RUN = re.compile(_MARKER.pattern + r"(?:\s*" + _MARKER.pattern.replace("(?<!\\[)", "") + r")*")
_FOOTNOTE_MARKER = re.compile(r"\[\^(\d{1,3})\]")
_DOUBLE_BRACKET_MARKER = re.compile(r"\[\[(\d{1,3}(?:\s*[,\-\u2013]\s*\d{1,3})*)\]\]")


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def role_key(user_role_from_db: Optional[str]) -> str:
    if not user_role_from_db:
        return "DEFAULT"
    return _ROLE_KEY_BY_PROFESSION.get(user_role_from_db, "DEFAULT")


def build_answer_prompt(
    *,
    query: str,
    patient_data: str,
    chat_history: str,
    deep_search: bool,
    user_role_from_db: Optional[str],
    sources: list[dict[str, Any]],
    jurisdiction_rule: str | None = None,
    max_references: int | None = None,
) -> str:
    """Assemble the full generation prompt.

    ``sources`` is an ordered list of dicts with ``number``, ``title``,
    ``source_label``, ``year``, ``url`` and ``excerpt``. The numbering here is
    the numbering the model must cite, so callers must pass the same list they
    later hand to ``finalize_answer`` as citations.
    """
    key = role_key(user_role_from_db)
    system = ANSWER_SYSTEM_PROMPT.format(
        role_instruction=ROLE_INSTRUCTIONS[key],
        jurisdiction_rule=(jurisdiction_rule or DEFAULT_JURISDICTION_RULE).strip(),
        depth_rule=DEEP_DEPTH_RULE if deep_search else QUICK_DEPTH_RULE,
        citation_cap_rule=_citation_cap_rule(max_references),
        exam_rule=EXAM_HANDLING if key in EXAM_ROLES else "",
    ).strip()

    context = _clean_block(patient_data)
    question = _clean_block(query)
    context_block = ""
    if context and context != question:
        context_block = f"\n## ADDITIONAL CONTEXT\n{context}\n"

    user_block = ANSWER_USER_BLOCK.format(
        query=question or "(empty question)",
        context_block=context_block,
        chat_history=_clean_block(chat_history) or "No previous conversation.",
        sources=format_sources_block(sources),
    )
    return f"{system}\n\n{user_block}"


def format_sources_block(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return NO_SOURCES_RULE
    lines: list[str] = []
    for source in sources:
        number = source.get("number")
        title = _compact(str(source.get("title") or f"Source {number}"))
        metadata = ", ".join(
            part
            for part in (
                _compact(str(source.get("source_label") or "")),
                str(source.get("year") or ""),
            )
            if part
        )
        header = f"[{number}] {title}" + (f" ({metadata})" if metadata else "")
        same_document_as = source.get("same_document_as")
        if same_document_as:
            header += f" - same document as [{same_document_as}], another page"
        excerpt = _compact(str(source.get("excerpt") or ""))
        lines.append(header + (f"\nExcerpt: {excerpt}" if excerpt else "\nExcerpt: (full text not extracted; treat as a verified source link only)"))
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Answer finalization
# ---------------------------------------------------------------------------


def finalize_answer(
    answer: str,
    citations: list[dict[str, Any]],
    *,
    max_references: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Return ``(display_markdown, used_citations)``.

    - Drops any References/Sources section the model wrote itself.
    - Normalizes ``[[1]]``, ``[^1]``, ``[1, 2]`` and ``[1](anything)`` to plain
      numeric markers, discards numbers that do not exist in ``citations``.
    - Groups citations by document (different pages of one PDF share a number),
      numbers documents in order of first use, and links each marker to the
      exact page or passage URL it came from.
    - Keeps at most ``max_references`` distinct documents; markers pointing at
      documents beyond the cap are removed rather than listed.
    - Appends a ``**References**`` list of the cited documents only. If the
      model cited nothing, no list is added.
    """
    body = strip_reference_section(answer or "").strip()
    if not citations:
        return _strip_all_markers(body), []

    by_original = {int(c.get("number") or index): c for index, c in enumerate(citations, start=1)}
    document_by_original = {
        original: citation_document_key(str(citation.get("url") or ""))
        for original, citation in by_original.items()
    }

    normalized = _DOUBLE_BRACKET_MARKER.sub(r"[\1]", body)
    normalized = _FOOTNOTE_MARKER.sub(r"[\1]", normalized)

    # First pass: documents in reading order, capped.
    document_order: list[str] = []
    for match in _MARKER.finditer(normalized):
        for original in _marker_numbers(match.group(1)):
            document = document_by_original.get(original)
            if document is None or document in document_order:
                continue
            if max_references is not None and len(document_order) >= max_references:
                continue
            document_order.append(document)
    display_by_document = {document: index for index, document in enumerate(document_order, start=1)}

    # Representative citation per document: the first-cited location.
    representative: dict[str, dict[str, Any]] = {}
    for match in _MARKER.finditer(normalized):
        for original in _marker_numbers(match.group(1)):
            document = document_by_original.get(original)
            if document in display_by_document and document not in representative:
                representative[document] = by_original[original]
    locations_per_document: dict[str, set[str]] = {}
    for original, document in document_by_original.items():
        if document in display_by_document:
            locations_per_document.setdefault(document, set()).add(
                citation_location_key(str(by_original[original].get("url") or ""))
            )

    def replace(run: re.Match[str]) -> str:
        links: list[str] = []
        seen: set[str] = set()
        for match in _MARKER.finditer(run.group(0)):
            for original in _marker_numbers(match.group(1)):
                document = document_by_original.get(original)
                display = display_by_document.get(document or "")
                if display is None:
                    continue
                url = str(by_original[original].get("url") or "").strip()
                key = f"{display}|{citation_location_key(url)}"
                if key in seen:
                    continue
                seen.add(key)
                links.append(f"[{display}]({url})" if url else f"[{display}]")
        return "".join(links)

    linked = _MARKER_RUN.sub(replace, normalized)
    linked = _tidy_marker_gaps(linked)

    if not document_order:
        # Nothing was cited, so there is nothing to reference. Listing every
        # retrieved candidate would dress an unsupported answer up as grounded.
        return linked, []

    used: list[dict[str, Any]] = []
    for document in document_order:
        citation = dict(representative[document], number=display_by_document[document])
        if len(locations_per_document.get(document, ())) > 1:
            citation["title"] = _strip_page_suffix(str(citation.get("title") or ""))
        used.append(citation)
    return f"{linked}\n\n{format_reference_list(used)}".strip(), used


def citation_document_key(url: str) -> str:
    """Identity of a document: the location key without a page anchor."""
    location = citation_location_key(url)
    return re.sub(r"#page=\d+$", "", location, flags=re.IGNORECASE)


def citation_location_key(url: str) -> str:
    """Identity of a citable location: the URL without a text-fragment anchor.

    ``#page=N`` anchors are kept because different PDF pages are different
    locations; ``#:~:text=...`` highlights are dropped because they only mark a
    passage on the same page.
    """
    cleaned = url.strip()
    cleaned = re.sub(r"#:~:text=.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(#page=\d+).*$", r"\1", cleaned, flags=re.IGNORECASE)
    if "#page=" not in cleaned.lower():
        cleaned = cleaned.split("#", 1)[0]
    return cleaned.rstrip("/").lower()


def strip_reference_section(answer: str) -> str:
    """Remove a trailing References/Sources section the model may have added."""
    lines = answer.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if _REFERENCES_HEADING.match(lines[index]):
            # Only treat it as a trailing section if everything after it looks like a list.
            tail = [line for line in lines[index + 1 :] if line.strip()]
            if all(re.match(r"^\s*(?:\d+[.)]|[-*•]|\[\d+\])\s*", line) for line in tail):
                return "\n".join(lines[:index]).rstrip()
    return answer


def format_reference_list(citations: list[dict[str, Any]]) -> str:
    lines = ["**References**", ""]
    for index, citation in enumerate(citations, start=1):
        lines.append(format_reference_line(index, citation))
    return "\n".join(lines)


def format_reference_line(index: int, citation: dict[str, Any]) -> str:
    title = _markdown_escape(reference_display_title(index, citation))
    url = str(citation.get("url") or "").strip()
    source = _markdown_escape(str(citation.get("source_label") or "")).strip()
    year = citation.get("year")
    metadata = ", ".join(part for part in (source, str(year) if year else "") if part)
    if url and metadata:
        return f"{index}. [{title}]({url}) - {metadata}"
    if url:
        return f"{index}. [{title}]({url})"
    if metadata:
        return f"{index}. {title} - {metadata}"
    return f"{index}. {title}"


GENERIC_TITLE_MAX_WORDS = 4
DOCUMENT_TITLE_MIN_WORDS = 5


def reference_display_title(index: int, citation: dict[str, Any]) -> str:
    title = clean_reference_title(str(citation.get("title") or ""))
    url = str(citation.get("url") or "").strip()
    source = str(citation.get("source_label") or "").strip()
    url_title = clean_reference_title(title_from_reference_url(url) or "")

    if _title_is_low_quality(title):
        title = (
            url_title
            if url_title and not _title_is_low_quality(url_title)
            else clean_reference_title(source or f"Source {index}")
        )

    # Crawled pages often carry the site's name rather than the document's, so a
    # reference reads "WHO Policy Platform" when the file is a national malaria
    # manual. The path usually holds the real name, but only some paths do, so
    # this swaps only when the metadata title is short enough to be a site name
    # and the path yields something long enough to be a document name.
    # Count the name itself: a trailing ", p. 16" is locator, not title.
    named_words = re.findall(r"[A-Za-z][A-Za-z'-]{1,}", _strip_page_suffix(title))
    if len(named_words) <= GENERIC_TITLE_MAX_WORDS:
        from_path = _document_title_from_path(url)
        if from_path:
            title = from_path
    return title or f"Source {index}"


def _document_title_from_path(url: str) -> str | None:
    """A document name recovered from a URL path, or None if the path has none."""
    raw = title_from_reference_url(url)
    if not raw:
        return None
    words: list[str] = []
    for word in clean_reference_title(raw).split():
        # Leading catalogue codes ("UGA CH 33 01") and language tags carry nothing.
        if not words and (word.isdigit() or (word.isupper() and len(word) <= 4)):
            continue
        if word.lower() in {"eng", "en", "fr", "fre", "spa", "final", "pdf", "version"}:
            continue
        # Trailing document ids carry nothing a reader can use.
        if word.isdigit() and len(word) >= 5:
            continue
        words.append(word if len(word) <= 4 or not word.isupper() else word.title())
    if len(words) < DOCUMENT_TITLE_MIN_WORDS:
        return None
    return " ".join(words)[:160].strip()


def clean_reference_title(title: str) -> str:
    cleaned = _compact(title)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"(?:https?://|www\.)\S+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\s*\|\s*", " | ", cleaned)
    cleaned = re.sub(r"^\d+(?:\.\d+){1,4}\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -.,;:") or "Source"


def title_from_reference_url(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    path = parsed.path.rstrip("/")
    if not path:
        return parsed.hostname.removeprefix("www.") if parsed.hostname else None
    segments = path.split("/")
    segment = segments[-1]
    if segment.lower() in {"content", "download", "pdf"} and len(segments) > 1:
        segment = segments[-2]
    if re.fullmatch(r"[0-9a-f-]{16,}", segment, flags=re.IGNORECASE):
        return None
    title = re.sub(r"\.(?:html?|pdf|docx?)$", "", segment, flags=re.IGNORECASE)
    title = title.replace("-", " ").replace("_", " ")
    title = re.sub(r"\s+", " ", title).strip()
    return title[:180] if title else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_all_markers(body: str) -> str:
    cleaned = _DOUBLE_BRACKET_MARKER.sub("", body)
    cleaned = _FOOTNOTE_MARKER.sub("", cleaned)
    cleaned = _MARKER.sub("", cleaned)
    return _tidy_marker_gaps(cleaned)


def _citation_cap_rule(max_references: int | None) -> str:
    if not max_references:
        return "Cite every source you actually rely on."
    return (
        f"Cite at most {max_references} different sources in the whole answer, choosing the most "
        "authoritative and directly relevant ones. Numbers marked as another page of the same "
        "document count as one source, and you may cite several of its pages."
    )


def _strip_page_suffix(title: str) -> str:
    return re.sub(r"[,;:\s]*\(?\bp(?:p|age)?\.?\s*\d+(?:\s*[-\u2013]\s*\d+)?\)?\s*$", "", title, flags=re.IGNORECASE).strip() or title


def _marker_numbers(group: str) -> list[int]:
    """Expand "1, 3" and "2-4" style marker contents into distinct numbers."""
    numbers: list[int] = []
    for part in re.split(r"\s*,\s*", group.strip()):
        range_match = re.fullmatch(r"(\d{1,3})\s*[-\u2013]\s*(\d{1,3})", part)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            candidates = range(start, end + 1) if start <= end else [start, end]
        elif part.isdigit():
            candidates = [int(part)]
        else:
            continue
        for number in candidates:
            if number not in numbers:
                numbers.append(number)
    return numbers


def _tidy_marker_gaps(text: str) -> str:
    # Only repair whitespace left behind where a marker was removed or relinked:
    # "word [x] ." -> "word." and "word  word" -> "word word". Nothing else.
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def _title_is_low_quality(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", title.lower()).strip()
    return bool(
        len(normalized) < 4
        or normalized in {"source", "clinical source", "content", "download", "full text", "pdf"}
        or re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/.*)?", normalized)
    )


def _markdown_escape(value: str) -> str:
    return re.sub(r"([\[\]])", r"\\\1", value)


def _compact(text: str) -> str:
    return " ".join(text.split())


def _clean_block(text: str | None) -> str:
    if not text:
        return ""
    stripped = text.strip()
    return stripped if stripped and stripped.lower() not in {"no previous conversation", "no additional context provided."} else ""
