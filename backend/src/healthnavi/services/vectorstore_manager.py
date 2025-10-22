from healthnavi.services.vectordb_service import ZillizService
from typing import Tuple, List
import time
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
    Extracts patient age for age-appropriate source prioritization.
    """
    manager_start = time.time()
    
    if not vectorstore_initialized:
        logger.error("Vector store not initialized.")
        raise RuntimeError("Vector store not initialized. Call initialize_vectorstore() at startup.")

    # Combine query and patient data
    full_search_query = f"{query}\n{patient_data}".strip()
    combined_length = len(full_search_query)
    
    # Extract patient age from query or patient data
    patient_age = extract_patient_age(full_search_query)
    
    logger.info(f"🔍 VectorStore Manager: Processing combined query ({combined_length} chars, patient_age={patient_age})")
    
    try:
        context, sources = vectordb_service.search_medical_knowledge(
            full_search_query, 
            k=k,
            patient_age=patient_age
        )
        
        manager_time = time.time() - manager_start
        logger.info(f"📋 VectorStore Manager completed in {manager_time:.3f}s")
        
        return context, sources
    except Exception as e:
        manager_time = time.time() - manager_start
        logger.error(f"Error searching collections (took {manager_time:.3f}s): {e}")
        return f"An error occurred during search: {str(e)}", []

def extract_patient_age(text: str) -> int:
    """
    Extract patient age from query or patient data text.
    Returns None if age cannot be determined.
    
    Examples:
        "65-year-old woman" -> 65
        "5 year old child" -> 5
        "68-year-old male" -> 68
        "Patient is 42 years old" -> 42
    """
    import re
    
    # Pattern 1: "X-year-old" or "X year old" or "X y/o" or "X yo"
    pattern1 = r'\b(\d{1,3})\s*[-\s]*(year|yr|y)[\s-]*(old|o)\b'
    match = re.search(pattern1, text.lower())
    if match:
        age = int(match.group(1))
        logger.info(f"📅 Extracted patient age: {age} years")
        return age
    
    # Pattern 2: "X years old" or "aged X"
    pattern2 = r'\b(?:aged|age)\s+(\d{1,3})\b|\b(\d{1,3})\s+years?\s+old\b'
    match = re.search(pattern2, text.lower())
    if match:
        age = int(match.group(1) or match.group(2))
        logger.info(f"📅 Extracted patient age: {age} years")
        return age
    
    # Pattern 3: Month old (for infants) - convert to 0
    pattern3 = r'\b(\d{1,2})\s*[-\s]*(month|mo)[\s-]*(old|o)\b'
    match = re.search(pattern3, text.lower())
    if match:
        logger.info(f"📅 Extracted patient age: infant (<1 year)")
        return 0
    
    logger.info("📅 Could not extract patient age from query")
    return None
    