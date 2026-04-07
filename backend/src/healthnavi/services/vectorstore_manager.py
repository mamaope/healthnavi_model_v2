from healthnavi.services.vectordb_service import get_vectordb_service
from typing import Tuple, List
import logging
import os
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# get_vectordb_service() is lazy; connection happens on first use
vectorstore_initialized = False

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
        logger.warning("Vector store not ready yet (still warming up).")
        raise RuntimeError("Knowledge base is still starting up. Please try again in a moment.")

    full_search_query = f"{query.strip()}\n{patient_data.strip()}".strip()

    try:
        # Retrieve more chunks than needed so post-filtering can still return max_chunks
        retrieval_multiplier = 2 if max_chunks <= 8 else 3
        raw_chunks, all_sources = vectordb_service.search_medical_knowledge(
            full_search_query,
            k=max_chunks * retrieval_multiplier
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
            top_chunks = raw_chunks[:max_chunks]

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
    