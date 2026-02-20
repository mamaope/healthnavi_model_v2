from __future__ import annotations

import logging
import os
from typing import List, Tuple
from collections import defaultdict

from healthnavi.services.vectordb_service import vectordb_service
from healthnavi.core.constants import SHORT_QUERY_WORD_THRESHOLD

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

vectorstore_initialized = False


def initialize_vectorstore() -> None:
    global vectorstore_initialized
    if vectorstore_initialized:
        return

    ok = vectordb_service.ping()
    if not ok:
        raise RuntimeError("Qdrant is not reachable (ping failed). Check QDRANT_URL / network / firewall.")
    vectorstore_initialized = True
    logger.info("✅ Vectorstore initialized: Qdrant reachable.")


def search_all_collections(
    query: str,
    patient_data: str,
    max_chunks: int = 20,
    max_books: int = 8,
    min_chunks: int = 5,
    min_books: int = 3,
    deep_search: bool = False,
) -> Tuple[List[dict], List[str]]:
    """
    Retrieval strategy:
      - sparse_query: always raw query (best for drug names/abbrev)
      - dense_query:
          * short query: raw query
          * longer query: raw query + patient context (if provided)
    """
    if not vectorstore_initialized:
        initialize_vectorstore()

    clean_query = (query or "").strip()
    patient_context = (patient_data or "").strip()
    if not clean_query:
        return [], []

    word_count = len(clean_query.split())

    sparse_query = clean_query
    if word_count <= SHORT_QUERY_WORD_THRESHOLD:
        dense_query = clean_query
    else:
        dense_query = f"{clean_query}\n{patient_context}" if patient_context else clean_query

    retrieve_k = max_chunks * 2  # pull extra then diversity-filter

    raw_chunks, all_sources = vectordb_service.search_medical_knowledge(
        dense_query=dense_query,
        k=retrieve_k,
        sparse_query=sparse_query,
        deep_search=deep_search,
    )

    # Pneumonia keyword filter after retrieval
    q = (query or "").lower()
    if "pneumonia" in q:
        pneumonia_only = [c for c in raw_chunks if "pneumonia" in (c.get("content", "").lower())]
        if len(pneumonia_only) >= min_chunks:
            raw_chunks = pneumonia_only
        else:
            # If that leaves too few, allow these too
            raw_chunks = [c for c in raw_chunks if any(kw in (c.get("content", "").lower()) for kw in ["pneumonia", "fast breathing", "chest indrawing", "amoxicillin", "imci"])]
    if not raw_chunks:
        logger.warning("No relevant context returned from vectordb_service.")
        return [], []

    # If it looks like a drug-name lookup, boost register/table-ish hits
    if _is_likely_drug_query(clean_query):
        raw_chunks = _boost_drug_register_chunks(raw_chunks)

    top_chunks = _apply_book_diversity(
        raw_chunks,
        max_chunks=max_chunks,
        max_books=max_books,
        min_chunks=min_chunks,
        min_books=min_books,
    )

    unique_sources = []
    seen = set()
    for c in top_chunks:
        fp = os.path.basename(c.get("file_path", "Unknown"))
        if fp not in seen:
            seen.add(fp)
            unique_sources.append(fp)

    return top_chunks, unique_sources


def _apply_book_diversity(
    chunks: List[dict],
    max_chunks: int = 20,
    max_books: int = 8,
    min_chunks: int = 5,
    min_books: int = 3,
) -> List[dict]:
    """
    Relevance-first with a diversity floor:
      1) Guarantee at least 1 chunk from each of top min_books sources (if possible)
      2) Fill remaining slots by global relevance, respecting max_books
    """
    if not chunks:
        return []

    # Group chunks by book, preserving order (= relevance order)
    book_chunks: dict[str, list] = defaultdict(list)
    for chunk in chunks:
        file_name = os.path.basename(chunk.get("file_path", "Unknown"))
        book_chunks[file_name].append(chunk)

    available_books = len(book_chunks)
    target_chunks = min(max(min_chunks, len(chunks)), max_chunks)

    if available_books <= 1:
        return chunks[:target_chunks]

    # If fewer books than min_books, just return top chunks
    if available_books < min_books:
        return chunks[:target_chunks]

    # Step 1: take best chunk from each of the first min_books books as they appear in ranked list
    ordered_books = []
    for c in chunks:
        b = os.path.basename(c.get("file_path", "Unknown"))
        if b not in ordered_books:
            ordered_books.append(b)

    seed_books = ordered_books[:min_books]
    selected = []
    selected_ids = set()
    books_represented = set()

    for b in seed_books:
        best = book_chunks[b][0]
        sid = id(best)
        if sid not in selected_ids:
            selected.append(best)
            selected_ids.add(sid)
            books_represented.add(b)

    # Step 2: fill remaining slots by relevance, enforcing max_books cap
    for c in chunks:
        if len(selected) >= target_chunks:
            break
        sid = id(c)
        if sid in selected_ids:
            continue
        b = os.path.basename(c.get("file_path", "Unknown"))
        if b not in books_represented and len(books_represented) >= max_books:
            continue
        selected.append(c)
        selected_ids.add(sid)
        books_represented.add(b)

    return selected


def _is_likely_drug_query(query: str) -> bool:
    words = query.strip().split()
    if len(words) > 4:
        return False

    q = query.lower()
    question_words = ["what", "how", "when", "why", "where", "who", "which", "should", "can", "does"]
    has_question_word = any(w in q for w in question_words)

    if len(words) <= 3 and not has_question_word:
        return True

    drug_indicators = ["mg", "tablet", "dose", "dosage", "drug", "medicine", "medication", "indication", "contraindication"]
    return any(ind in q for ind in drug_indicators)


def _boost_drug_register_chunks(chunks: List[dict]) -> List[dict]:
    """
    Boost likely drug-register/table chunks.
    Heuristics:
      - filename hints: drug/register/formulary
      - content/table hints
    """
    boosted = []
    rest = []

    for c in chunks:
        fp = (c.get("file_path") or "").lower()
        txt = (c.get("content") or "").lower()
        is_register = any(k in fp for k in ["drug", "register", "formulary", "eml", "essential"])
        is_tableish = any(k in txt for k in ["table", "strength", "dosage form", "active ingredient", "atc"])
        if is_register or is_tableish:
            boosted.append(c)
        else:
            rest.append(c)

    return boosted + rest
