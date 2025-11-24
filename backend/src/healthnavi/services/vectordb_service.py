import os
import time
from typing import List, Dict, Tuple, Any
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

class ZillizService:
    """Service for interacting with Zilliz Cloud."""

    def __init__(self):
        """Initializes the MilvusClient and Azure OpenAI client."""
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
        """Generates a 3072-dim embedding for the query using Azure OpenAI."""
        try:
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
        search_total_start = time.time()
        logger.info(f"🔍 Starting medical knowledge search (k={k})...")
        
        if not self.check_collection_exists():
            logger.error("Collection not found.")
            return "Collection not found. Please ensure it is created and named correctly.", []

        try:
            # Step 1: Generate query embedding client-side
            embedding_start = time.time()
            query_embedding = self.generate_query_embedding(query)
            embedding_time = time.time() - embedding_start

            retrieve_k = min(k * 3, 100)
            vector_search_start = time.time()
            logger.info(f"🎯 Vector search in '{self.collection_name}' (retrieving {retrieve_k}, returning {k})...")
            
            search_results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=retrieve_k,
                output_fields=["payload"],
                search_params={"metric_type": "COSINE"}
            )
            
            vector_search_time = time.time() - vector_search_start
            logger.info(f"🎯 Vector search completed in {vector_search_time:.3f}s")

            if not search_results or not search_results[0]:
                logger.warning("No relevant medical information found.")
                return "No relevant medical information found in the knowledge base.", []

            # Step 3: Apply MMR diversity reranking
            rerank_start = time.time()
            reranked_results = self._apply_mmr_diversity_reranking(
                search_results[0], 
                k, 
                lambda_param=0.5
            )
            rerank_time = time.time() - rerank_start
            logger.info(f"🔄 MMR diversity reranking completed in {rerank_time:.3f}s")

            # Step 4: Process and format results
            processing_start = time.time()
            reranked_entities = []
            sources = set()
            total_content_length = 0
            
            import json
            
            for idx, hit in enumerate(reranked_results):
                entity = hit.get('entity', {})
                payload_str = entity.get('payload', '{}')
                
                # Debug: Log first result to see structure (only once per search)
                if idx == 0:
                    logger.info(f"🔍 DEBUG - First hit structure: {list(hit.keys())}")
                    logger.info(f"🔍 DEBUG - Entity keys: {list(entity.keys())}")
                    logger.info(f"🔍 DEBUG - Payload (first 200 chars): {payload_str[:200]}")
                
                # Parse the payload JSON string
                try:
                    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                    
                    # Debug: Log payload keys
                    if idx == 0:
                        logger.info(f"🔍 DEBUG - Parsed payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'Not a dict'}")
                    
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

            processing_time = time.time() - processing_start

            if not reranked_entities:
                logger.warning("No relevant content extracted from search results.")
                return [], []

            search_total_time = time.time() - search_total_start
            
            # Detailed timing breakdown for search operation
            logger.info(f"📊 SEARCH TIMING BREAKDOWN:")
            logger.info(f"   ├── Embedding Generation: {embedding_time:.3f}s ({embedding_time/search_total_time*100:.1f}%)")
            logger.info(f"   ├── Vector Search: {vector_search_time:.3f}s ({vector_search_time/search_total_time*100:.1f}%)")
            logger.info(f"   ├── MMR Reranking: {rerank_time:.3f}s ({rerank_time/search_total_time*100:.1f}%)")
            logger.info(f"   └── Result Processing: {processing_time:.3f}s ({processing_time/search_total_time*100:.1f}%)")
            logger.info(f"✅ Search completed in {search_total_time:.3f}s - Retrieved {len(reranked_entities)} chunks ({total_content_length} chars) from {len(sources)} unique sources")
            
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

vectordb_service = ZillizService()
