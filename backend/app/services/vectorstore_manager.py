from app.services.vectordb_service import ZillizService
from typing import Tuple, List
import logging

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

def search_all_collections(query: str, patient_data: str, k: int = 8) -> Tuple[str, List[str]]:
    """
    Performs a search across the medical knowledge collection.
    Combines query and patient data for richer context.
    """
    if not vectorstore_initialized:
        logger.error("Vector store not initialized.")
        raise RuntimeError("Vector store not initialized. Call initialize_vectorstore() at startup.")

    full_search_query = f"{query}\n{patient_data}".strip()
    try:
        return vectordb_service.search_medical_knowledge(full_search_query, k=k)
    except Exception as e:
        logger.error(f"Error searching collections: {e}")
        return f"An error occurred during search: {str(e)}", []
