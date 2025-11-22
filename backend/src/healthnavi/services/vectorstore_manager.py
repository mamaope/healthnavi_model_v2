from healthnavi.services.vectordb_service import ZillizService
from typing import Tuple, List
import time
import logging
import os

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

def search_all_collections(query: str, patient_data: str, k: int = 3) -> Tuple[List, List[str]]:
    """
    Perform semantic retrieval and return optimized context for LLM.
    - Only top-k chunks (most relevant) are included.
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
        # OPTIMIZATION: Retrieve only 2x chunks
        # This reduces vector search time significantly
        raw_chunks, all_sources = vectordb_service.search_medical_knowledge(full_search_query, k=k*2)

        if not raw_chunks or not all_sources:
            logger.warning("No relevant context found by vectordb_service.")
            return [], []
        
        # OPTIMIZATION: Skip enrichment to avoid extra DB queries
        # Use raw chunks directly - they already have all needed information
        top_chunks = raw_chunks[:k]

        unique_top_sources = set()
        for chunk in top_chunks:
            file_name = os.path.basename(chunk.get("file_path", "Unknown document"))
            # Clean up source name: remove .pdf extension and clean formatting
            file_name = file_name.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
            unique_top_sources.add(file_name)

        total_time = time.time() - start_time
        logger.info(f"� Retrieved {len(top_chunks)} top chunks in {total_time:.2f}s from {len(unique_top_sources)} sources.")
        return top_chunks, list(unique_top_sources)

    except Exception as e:
        logger.error(f"❌ Error during search_all_collections: {e}", exc_info=True)
        return [], []
    