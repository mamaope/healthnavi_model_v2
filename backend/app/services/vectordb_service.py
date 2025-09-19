import os
from typing import List, Dict, Tuple
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
            response = self.azure_client.embeddings.create(
                input=[query],
                model=self.azure_deployment
            )
            embedding = response.data[0].embedding
            logger.info("Successfully generated query embedding.")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise

    def search_medical_knowledge(self, query: str, k: int = 5) -> Tuple[str, List[str]]:
        """
        Searches the medical knowledge collection using a client-side Azure OpenAI embedding.
        Returns context and source citations.
        """
        if not self.check_collection_exists():
            logger.error("Collection not found.")
            return "Collection not found. Please ensure it is created and named correctly.", []

        try:
            # Generate query embedding client-side
            query_embedding = self.generate_query_embedding(query)

            # Search with the embedding
            search_results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=k,
                output_fields=["content", "file_path", "page_number"],
                search_params={"metric_type": "COSINE"}
            )

            if not search_results or not search_results[0]:
                logger.warning("No relevant medical information found.")
                return "No relevant medical information found in the knowledge base.", []

            # Process results
            context_parts = []
            sources = set()
            for hit in search_results[0]:
                entity = hit.get('entity', {})
                content = entity.get('content')
                if content:
                    context_parts.append(content)
                    file_path = entity.get('file_path', 'Unknown document')
                    page_number = entity.get('page_number', 'N/A')
                    source_str = f"{os.path.basename(file_path)} (Page: {page_number})"
                    sources.add(source_str)

            if not context_parts:
                logger.warning("No relevant content extracted from search results.")
                return "No relevant medical information found in the knowledge base.", []

            full_context = "\n".join(context_parts)
            logger.info(f"Retrieved {len(context_parts)} chunks with {len(sources)} unique sources.")
            return full_context, sorted(list(sources))

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
