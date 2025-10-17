from typing import Tuple, List
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import the real ZillizService
try:
    from healthnavi.services.vectordb_service import vectordb_service
    logger.info("Loaded real ZillizService from vectordb_service")
except ImportError as e:
    logger.warning(f"Failed to import real ZillizService: {e}")
    logger.warning("Using placeholder ZillizService")
    
    class ZillizService:
        """Placeholder Zilliz service."""
        
        def __init__(self):
            logger.warning("ZillizService is not implemented - using placeholder")
            self.collection_name = "medical_knowledge"
        
        def search(self, query: str, collection_name: str = "medical_knowledge", limit: int = 5) -> List[dict]:
            """Placeholder search method."""
            logger.warning(f"ZillizService.search called with query: {query[:50]}...")
            return []
        
        def load_collection(self):
            """Placeholder load collection method."""
            logger.warning("ZillizService.load_collection called - placeholder implementation")
            return True
        
        def search_medical_knowledge(self, query: str, k: int = 8) -> Tuple[str, List[str]]:
            """Placeholder search medical knowledge method."""
            logger.warning(f"ZillizService.search_medical_knowledge called with query: {query[:50]}...")
            return "No vector store available - using AI without RAG context", []
    
    vectordb_service = ZillizService()

# Global variable to track vector store initialization status
vectorstore_initialized = False

def initialize_vectorstore():
    """Initializes and loads the Zilliz collection at startup."""
    global vectorstore_initialized
    if not vectorstore_initialized:
        logger.info("Initializing vector store...")
        try:
            vectordb_service.load_collection()
            vectorstore_initialized = True
            logger.info("Vector store initialized successfully.")
        except Exception as e:
            logger.warning(f"Vector store initialization failed: {e}")
            logger.warning("Continuing without vector store - AI will work without RAG context")
            # Don't raise error, just mark as not initialized
            vectorstore_initialized = False

def search_all_collections(query: str, patient_data: str, k: int = 8) -> Tuple[str, List[str]]:
    """
    Performs a search across the medical knowledge collection.
    Combines query and patient data for richer context.
    """
    global vectorstore_initialized
    if not vectorstore_initialized:
        logger.warning("Vector store not initialized - returning empty context")
        return "No vector store available - using AI without RAG context", []

    full_search_query = f"{query}\n{patient_data}".strip()
    try:
        return vectordb_service.search_medical_knowledge(full_search_query, k=k)
    except Exception as e:
        logger.error(f"Error searching collections: {e}")
        return f"An error occurred during search: {str(e)}", []
