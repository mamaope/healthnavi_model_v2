from healthnavi.services.vectordb_service import ZillizService
from typing import Tuple, List
import time
import logging
import os
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize ZillizService once
vectordb_service = ZillizService()
vectorstore_initialized = False

def initialize_vectorstore():
    """Initializes and loads the Zilliz collection at startup."""
    global vectorstore_initialized
    if not vectorstore_initialized:
        logger.info("Initializing and loading Zilliz collection...")
        try:
            vectordb_service.load_collection()
            vectorstore_initialized = True
            logger.info("Zilliz collection loaded and ready.")
        except Exception as e:
            error_message = f"CRITICAL: Could not load collection '{vectordb_service.collection_name}'. Error: {e}"
            logger.error(error_message)
            raise RuntimeError(error_message)

def search_all_collections(query: str, patient_data: str, k: int = 20) -> Tuple[List, List[str]]:
    """
    Perform semantic retrieval and return optimized context for LLM.
    - Retrieves k chunks with diversity across multiple books.
    """
    start_time = time.time()
    client = vectordb_service.client
    collection_name = vectordb_service.collection_name

    if not vectorstore_initialized or not client:
        logger.error("Vector store not initialized.")
        raise RuntimeError("Vector store not initialized. Call initialize_vectorstore() first.")

    full_search_query = f"{query.strip()}\n{patient_data.strip()}".strip()
    logger.info(f"🔍 Running semantic retrieval (query length={len(full_search_query)})")

    try:
        # Retrieve more chunks to ensure diversity across multiple books
        raw_chunks, all_sources = vectordb_service.search_medical_knowledge(full_search_query, k=k*3)

        if not raw_chunks or not all_sources:
            logger.warning("No relevant context found by vectordb_service.")
            return [], []
        
        # Apply book diversity: ensure we get chunks from multiple different books
        top_chunks = _apply_book_diversity(raw_chunks, target_chunks=k, min_books=8)

        unique_top_sources = set()
        for chunk in top_chunks:
            file_name = os.path.basename(chunk.get("file_path", "Unknown document"))
            # Clean up source name: remove .pdf extension and clean formatting
            file_name = file_name.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
            unique_top_sources.add(file_name)

        total_time = time.time() - start_time
        logger.info(f"📚 Retrieved {len(top_chunks)} top chunks in {total_time:.2f}s from {len(unique_top_sources)} sources.")
        return top_chunks, list(unique_top_sources)

    except Exception as e:
        logger.error(f"❌ Error during search_all_collections: {e}", exc_info=True)
        return [], []


def _apply_book_diversity(chunks: List, target_chunks: int = 20, min_books: int = 8) -> List:
    """
    Apply book diversity to ensure chunks come from multiple different books.
    
    Args:
        chunks: List of all retrieved chunks
        target_chunks: Number of chunks to return
        min_books: Minimum number of different books to include
        
    Returns:
        List of chunks with diversity across books
    """
    if not chunks:
        return [] 
    
    book_chunks = defaultdict(list)
    for chunk in chunks:
        file_name = os.path.basename(chunk.get("file_path", "Unknown"))
        book_chunks[file_name].append(chunk)
    
    # If we have fewer books than min_books, just return top chunks
    if len(book_chunks) < min_books:
        logger.warning(f"Only {len(book_chunks)} books found, less than minimum {min_books}")
        return chunks[:target_chunks]
    
    # Distribute chunks across books round-robin to ensure diversity
    selected_chunks = []
    book_lists = list(book_chunks.values())
    book_names = list(book_chunks.keys())
    
    # First, get at least one chunk from each of the top min_books books
    for i in range(min_books):
        if i < len(book_lists) and book_lists[i]:
            selected_chunks.append(book_lists[i].pop(0))
    
    book_idx = 0
    while len(selected_chunks) < target_chunks:
        # Find next book with remaining chunks
        attempts = 0
        while attempts < len(book_lists):
            if book_idx >= len(book_lists):
                book_idx = 0
            if book_lists[book_idx]:
                selected_chunks.append(book_lists[book_idx].pop(0))
                book_idx += 1
                break
            book_idx += 1
            attempts += 1
        
        # If no more chunks available, break
        if attempts >= len(book_lists):
            break
    
    logger.info(f"📖 Diversity selection: {len(selected_chunks)} chunks from {len(set(os.path.basename(c.get('file_path', '')) for c in selected_chunks))} different books")
    return selected_chunks
    