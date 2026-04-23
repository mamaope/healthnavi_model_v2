from healthnavi.services.vectordb_service import get_vectordb_service
from typing import Tuple, List
import logging
import os
import re
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# get_vectordb_service() is lazy; connection happens on first use
vectorstore_initialized = False


def _extract_jurisdiction_terms(query: str, patient_data: str) -> set[str]:
    """
    Extract explicit jurisdiction-like mentions without hardcoded country/stopword lists.
    Strategy:
    - look for named entities after in/for/from/within (title case or ALL CAPS)
    - keep short phrase + token forms for flexible source-name matching
    """
    text = f"{query or ''} {patient_data or ''}".strip()
    if not text:
        return set()

    terms: set[str] = set()
    named_loc_pattern = (
        r"(?i)\b(?:in|for|from|within)\s+"
        r"([A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+){0,2}|[A-Z]{2,}(?:\s+[A-Z]{2,}){0,2})"
    )
    for match in re.finditer(named_loc_pattern, text):
        phrase = re.sub(r"\s+", " ", match.group(1)).strip()
        if not phrase:
            continue
        terms.add(phrase.lower())
        for token in phrase.split():
            if len(token) >= 3:
                terms.add(token.lower())

    return terms


def _source_priority_score(chunk: dict, query: str, patient_data: str) -> int:
    """
    Score chunks for guideline authority relevance and jurisdiction fit.
    """
    source_path_text = f"{chunk.get('file_path', '')}".lower()
    source_text = f"{chunk.get('file_path', '')} {chunk.get('content', '')}".lower()
    query_text = f"{query or ''} {patient_data or ''}".lower()
    score = 0

    jurisdiction_terms = _extract_jurisdiction_terms(query, patient_data)
    if jurisdiction_terms:
        if any(term in source_path_text for term in jurisdiction_terms):
            score += 12

    # Prefer official and guideline-like documents when query asks policy/guideline questions.
    asks_for_guidance = any(
        k in query_text
        for k in ("guidelines", "protocol", "best practice", "recommendation", "policy")
    )
    if asks_for_guidance:
        if any(k in source_text for k in ("guidelines", "protocol", "standard treatment", "clinical policy")):
            score += 5
        if any(k in source_text for k in ("ministry of health", "department of health", "national")):
            score += 4

    # Trusted global institutions are useful fallback when local guidance is not present.
    if any(k in source_text for k in ("who", "nice", "cdc", "idsa", "ema", "fda")):
        score += 2

    return score


def _build_enriched_retrieval_query(query: str, patient_data: str) -> str:
    """
    Build a single retrieval query 
    """
    base_query = f"{(query or '').strip()}\n{(patient_data or '').strip()}".strip()
    query_text = f"{query or ''} {patient_data or ''}".lower()
    jurisdiction_terms = _extract_jurisdiction_terms(query, patient_data)
    asks_for_guidance = any(
        k in query_text
        for k in ("guideline", "protocol", "best practice", "recommendation", "policy")
    )

    enrichment_terms: list[str] = []
    if jurisdiction_terms:
        enrichment_terms.extend(sorted(jurisdiction_terms))
        # Repeat jurisdiction terms to increase sparse retrieval weight without extra calls.
        enrichment_terms.extend(sorted(jurisdiction_terms))
        enrichment_terms.extend(["country-specific", "national treatment guideline", "local protocol"])
    if asks_for_guidance:
        enrichment_terms.extend(
            ["national guideline", "ministry of health", "department of health", "clinical protocol"]
        )

    if not enrichment_terms:
        return base_query

    enrichment = " ".join(enrichment_terms)
    return f"{base_query}\n{enrichment}".strip()

def initialize_vectorstore():
    """Initializes and loads the Zilliz collection at startup. Connects to Zilliz on first use (lazy)."""
    global vectorstore_initialized
    if not vectorstore_initialized:
        logger.info("Initializing and loading Zilliz collection...")
        try:
            vectordb_service = get_vectordb_service()
            vectordb_service.load_collection()
            vectorstore_initialized = True
            logger.info("Zilliz collection loaded and ready.")
        except Exception as e:
            coll_name = os.getenv("MILVUS_COLLECTION_NAME", "medical_knowledge")
            error_message = f"CRITICAL: Could not load collection '{coll_name}'. Error: {e}"
            logger.error(error_message)
            raise RuntimeError(error_message)

def search_all_collections(
    query: str,
    patient_data: str,
    max_chunks: int = 20,
    max_books: int = 8,
    min_chunks: int = 5,
    min_books: int = 3,
    enforce_diversity: bool = False,  
) -> Tuple[List, List[str]]:
    """
    Perform semantic retrieval and return optimized context for LLM.

    Key change:
      - Quick search (enforce_diversity=False): prioritize topic accuracy (no round-robin across books)
      - Deep search  (enforce_diversity=True): apply book diversity AFTER retrieval to broaden references
    """
    vectordb_service = get_vectordb_service()
    client = vectordb_service.client
    collection_name = vectordb_service.collection_name

    if not vectorstore_initialized or not client:
        logger.error("Vector store not initialized.")
        raise RuntimeError("Vector store not initialized. Call initialize_vectorstore() first.")

    full_search_query = _build_enriched_retrieval_query(query, patient_data)

    try:
        # Retrieve more chunks than needed so post-filtering can still return max_chunks
        retrieval_multiplier = 2 if max_chunks <= 8 else 3
        if _extract_jurisdiction_terms(query, patient_data):
            # Expand candidate recall for country-specific questions;
            # still a single retrieval call, just broader top-k.
            retrieval_multiplier = max(retrieval_multiplier, 5)
        retrieval_k = max_chunks * retrieval_multiplier

        raw_chunks, all_sources = vectordb_service.search_medical_knowledge(
            full_search_query,
            k=retrieval_k
        )

        if not raw_chunks:
            logger.warning("No relevant context found by vectordb_service.")
            return [], []

        # only apply book diversity for deep search
        if enforce_diversity:
            top_chunks = _apply_book_diversity(
                raw_chunks,
                max_chunks=max_chunks,
                max_books=max_books,
                min_chunks=min_chunks,
                min_books=min_books
            )
        else:
            # Quick mode: strict relevance first (top-k only)
            # Re-rank by authority/jurisdiction fit, then keep retrieval relevance order as tiebreaker.
            scored_chunks = sorted(
                enumerate(raw_chunks),
                key=lambda it: (-_source_priority_score(it[1], query, patient_data), it[0]),
            )
            top_chunks = [raw_chunks[idx] for idx, _ in scored_chunks[:max_chunks]]

        jurisdiction_terms = _extract_jurisdiction_terms(query, patient_data)
        if jurisdiction_terms:
            matched_local = 0
            for chunk in top_chunks:
                src = f"{chunk.get('file_path', '')} {chunk.get('content', '')}".lower()
                if any(term in src for term in jurisdiction_terms):
                    matched_local += 1
            logger.info(
                "Jurisdiction-aware retrieval: terms=%s, candidates=%s, local_matches_in_top=%s",
                sorted(jurisdiction_terms),
                len(raw_chunks),
                matched_local,
            )

        # Build unique sources
        unique_top_sources = set()
        for chunk in top_chunks:
            file_name = os.path.basename(chunk.get("file_path", "Unknown document"))
            file_name = file_name.replace(".pdf", "").replace("_", " ").replace("-", " ")
            unique_top_sources.add(file_name)

        return top_chunks, sorted(list(unique_top_sources))

    except Exception as e:
        logger.error(f"❌ Error during search_all_collections: {e}", exc_info=True)
        return [], []

def _apply_book_diversity(
    chunks: List, 
    max_chunks: int = 20,
    max_books: int = 8,
    min_chunks: int = 5,
    min_books: int = 3
) -> List:
    """
    Apply source diversity to ensure chunks come from multiple different sources.
    Ensures minimums for diversity while respecting maximums.
    """
    if not chunks:
        return [] 
    
    book_chunks = defaultdict(list)
    for chunk in chunks:
        file_name = os.path.basename(chunk.get("file_path", "Unknown"))
        book_chunks[file_name].append(chunk)
    
    available_books = len(book_chunks)
    
    # Ensure we have at least min_books, but don't exceed max_books
    target_books = min(max(min_books, available_books), max_books)
    
    # Ensure we have at least min_chunks, but don't exceed max_chunks
    target_chunks = min(max(min_chunks, len(chunks)), max_chunks)
    
    # If we have fewer books than min_books, just return top chunks up to max_chunks
    if available_books < min_books:
        logger.warning(f"Only {available_books} books found, less than minimum {min_books}")
        return chunks[:target_chunks]
    
    # Distribute chunks across books round-robin to ensure diversity
    selected_chunks = []
    book_lists = list(book_chunks.values())[:target_books]  # Limit to max_books
    
    # First, get at least one chunk from each of the target_books
    for i in range(min(target_books, len(book_lists))):
        if book_lists[i]:
            selected_chunks.append(book_lists[i].pop(0))
    
    # Continue round-robin until we reach target_chunks or run out
    book_idx = 0
    while len(selected_chunks) < target_chunks:
        # Find next book with remaining chunks
        attempts = 0
        found = False
        while attempts < len(book_lists):
            if book_idx >= len(book_lists):
                book_idx = 0
            if book_lists[book_idx]:
                selected_chunks.append(book_lists[book_idx].pop(0))
                book_idx += 1
                found = True
                break
            book_idx += 1
            attempts += 1
        
        # If no more chunks available, break
        if not found:
            break
    
    return selected_chunks
    