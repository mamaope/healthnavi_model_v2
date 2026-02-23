import os
import time
import hashlib
from typing import List, Dict, Tuple, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymilvus import MilvusClient
import openai
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Embedding cache to avoid regenerating embeddings for the same queries
# Cache key: query hash -> (embedding, timestamp)
EMBEDDING_CACHE: Dict[str, Tuple[List[float], datetime]] = {}
EMBEDDING_CACHE_TTL_MINUTES = 60  # Cache embeddings for 1 hour
MAX_EMBEDDING_CACHE_SIZE = 500  # Maximum cached embeddings

def _get_embedding_cache_key(query: str) -> str:
    """Generate cache key for embedding."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

def _get_cached_embedding(query: str) -> List[float] | None:
    """Get cached embedding if available and not expired."""
    cache_key = _get_embedding_cache_key(query)
    if cache_key in EMBEDDING_CACHE:
        embedding, timestamp = EMBEDDING_CACHE[cache_key]
        if datetime.now() - timestamp < timedelta(minutes=EMBEDDING_CACHE_TTL_MINUTES):
            logger.info(f"⚡ Embedding cache HIT (age: {(datetime.now() - timestamp).seconds}s)")
            return embedding
        else:
            # Expired, remove from cache
            del EMBEDDING_CACHE[cache_key]
    return None

def _cache_embedding(query: str, embedding: List[float]):
    """Cache an embedding with timestamp."""
    cache_key = _get_embedding_cache_key(query)
    EMBEDDING_CACHE[cache_key] = (embedding, datetime.now())
    
    # Cleanup old entries if cache gets too large
    if len(EMBEDDING_CACHE) > MAX_EMBEDDING_CACHE_SIZE:
        sorted_keys = sorted(EMBEDDING_CACHE.keys(), key=lambda k: EMBEDDING_CACHE[k][1])
        for key in sorted_keys[:50]:  # Remove 50 oldest
            del EMBEDDING_CACHE[key]
        logger.info(f"🧹 Embedding cache cleanup - Removed 50 oldest entries")

class ZillizService:
    """Service for interacting with Zilliz Cloud."""

    def __init__(self):
        """Initializes the MilvusClient and Azure OpenAI client.
        Uses MILVUS_URI and MILVUS_TOKEN from env (Zilliz Cloud token auth).
        If you see 'auth check failure, please check username and password' from gRPC,
        the token is wrong/expired or not set in the environment (e.g. in Docker).
        """
        try:
            self.client = MilvusClient(
                uri=os.getenv('MILVUS_URI'),
                token=os.getenv('MILVUS_TOKEN')
            )
            self.collection_name = os.getenv('MILVUS_COLLECTION_NAME', 'medical_knowledge')
            self.azure_client = openai.AzureOpenAI(
                azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
                api_key=os.getenv('AZURE_OPENAI_API_KEY'),
                api_version=os.getenv('API_VERSION', '2024-02-01')
            )
            self.azure_deployment = os.getenv('DEPLOYMENT', 'text-embedding-3-large')
            logger.info("Milvus and Azure OpenAI clients initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise

    def check_collection_exists(self) -> bool:
        """Checks if the configured collection exists in Zilliz."""
        try:
            exists = self.client.has_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking for collection '{self.collection_name}': {e}")
            return False

    def generate_query_embedding(self, query: str) -> list[float]:
        """Generates a 3072-dim embedding for the query using Azure OpenAI.
        Uses caching to avoid regenerating embeddings for the same queries.
        """
        try:
            # Check cache first
            cached_embedding = _get_cached_embedding(query)
            if cached_embedding:
                return cached_embedding
            
            # Generate new embedding
            embedding_start = time.time()
            query_length = len(query)
            logger.info(f"🔢 Starting embedding generation for query ({query_length} chars)...")
            
            response = self.azure_client.embeddings.create(
                input=[query],
                model=self.azure_deployment
            )
            embedding = response.data[0].embedding
            
            embedding_time = time.time() - embedding_start
            logger.info(f"✨ Embedding generation completed in {embedding_time:.3f}s - Vector dim: {len(embedding)}")
            
            # Cache the embedding
            _cache_embedding(query, embedding)
            
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise

    def _apply_mmr_diversity_reranking(self, search_results: list, k: int, lambda_param: float = 0.5) -> list:
        """
        Apply Maximal Marginal Relevance (MMR) diversity reranking to the search results.
        
        Args:
            search_results (list): List of search results to rerank.
            k (int): Number of results to return.
            lambda_param (float): Trade-off parameter between relevance and diversity (0 to 1).
            
        Returns:
            list: Reranked list of results.
        """

        if not search_results:
            return []
            
        search_results.sort(key=lambda x: x.get('distance', 0), reverse=True)
        return search_results[:k]

    def search_medical_knowledge(self, query: str, k: int = 8) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Searches the medical knowledge collection using semantic similarity.
        Applies MMR diversity reranking to ensure balanced representation across sources.
        Returns context and source citations.
        
        Args:
            query: Search query text
            k: Number of results to return
        """
        if not self.check_collection_exists():
            logger.error("Collection not found.")
            return "Collection not found. Please ensure it is created and named correctly.", []

        try:
            query_embedding = self.generate_query_embedding(query)

            # Request fewer candidates for small k to speed up quick search
            retrieve_k = min(k * 2, 80) if k <= 16 else min(k * 3, 100)
            
            search_results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=retrieve_k,
                output_fields=["payload"],
                search_params={"metric_type": "COSINE"}
            )

            if not search_results or not search_results[0]:
                logger.warning("No relevant medical information found.")
                return "No relevant medical information found in the knowledge base.", []

            reranked_results = self._apply_mmr_diversity_reranking(
                search_results[0], 
                k, 
                lambda_param=0.5
            )

            reranked_entities = []
            sources = set()
            total_content_length = 0
            
            import json
            
            for idx, hit in enumerate(reranked_results):
                entity = hit.get('entity', {})
                payload_str = entity.get('payload', '{}')
                
                # Parse the payload JSON string
                try:
                    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                    
                    # Handle both new format (with chunk_text) and old format (without)
                    # New format: has 'chunk_text' field
                    # Old format: doesn't have chunk_text, we need to skip it OR show warning
                    content = payload.get('chunk_text', '')
                    
                    # If no chunk_text, this is old format data - log a warning
                    if not content:
                        if idx == 0:
                            logger.warning(f"⚠️  Old format detected: payload missing 'chunk_text' field. Data needs re-ingestion.")
                            logger.warning(f"⚠️  Available fields: {list(payload.keys())}")
                        continue
                    
                    # Extract other fields with fallbacks
                    file_path = payload.get('file_path') or payload.get('filename') or payload.get('source', 'Unknown document')
                    display_page_number = payload.get('display_page_number') or payload.get('page', '?')
                    
                    # Create a normalized entity structure
                    normalized_entity = {
                        'content': content,
                        'file_path': file_path,
                        'display_page_number': display_page_number
                    }
                    reranked_entities.append(normalized_entity)
                    document_name = os.path.basename(file_path)                    
                    sources.add(document_name)
                    total_content_length += len(content)
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse payload JSON: {str(e)} - {payload_str[:100]}...")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing hit {idx}: {str(e)}")
                    continue

            if not reranked_entities:
                logger.warning("No relevant content extracted from search results.")
                return [], []

            return reranked_entities, sorted(list(sources))

        except Exception as e:
            logger.error(f"Error during search in '{self.collection_name}': {e}")
            return f"An error occurred during search: {str(e)}", []

    def load_collection(self):
        """Loads the collection into memory for faster searches."""
        try:
            self.client.load_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load collection '{self.collection_name}': {e}")
            raise

_vectordb_instance: "ZillizService | None" = None

def get_vectordb_service() -> ZillizService:
    """Return the singleton ZillizService, creating it on first use (lazy init).
    This allows scripts that do not use the vector DB (e.g. seed_admin_user) to run
    without requiring a valid MILVUS_URI / MILVUS_TOKEN.
    """
    global _vectordb_instance
    if _vectordb_instance is None:
        _vectordb_instance = ZillizService()
    return _vectordb_instance

class _VectordbServiceProxy:
    """Proxy so existing code using vectordb_service.* does not connect at import time."""

    def _svc(self) -> ZillizService:
        return get_vectordb_service()

    @property
    def client(self):
        return self._svc().client

    @property
    def collection_name(self) -> str:
        return self._svc().collection_name

    def check_collection_exists(self) -> bool:
        return self._svc().check_collection_exists()

    def generate_query_embedding(self, query: str) -> list[float]:
        return self._svc().generate_query_embedding(query)

    def search_medical_knowledge(self, query: str, k: int = 8) -> Tuple[List[Dict[str, Any]], List[str]]:
        return self._svc().search_medical_knowledge(query, k=k)

    def load_collection(self) -> None:
        self._svc().load_collection()

vectordb_service = _VectordbServiceProxy()
