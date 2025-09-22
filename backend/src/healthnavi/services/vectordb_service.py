"""
Vector Database Service for HealthNavi AI CDSS.

This module provides integration with Zilliz Cloud (Milvus) for medical knowledge retrieval.
"""

import os
import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from pymilvus import connections, Collection, utility
import requests
import json

logger = logging.getLogger(__name__)


class ZillizService:
    """Service for interacting with Zilliz Cloud (Milvus) vector database."""
    
    def __init__(self):
        """Initialize Zilliz service with configuration from environment variables."""
        self.uri = os.getenv("MILVUS_URI")
        self.token = os.getenv("MILVUS_TOKEN")
        self.db_name = os.getenv("MILVUS_DB_NAME", "default")
        self.collection_name = os.getenv("MILVUS_COLLECTION_NAME", "medical_knowledge")
        self.drug_collection_name = os.getenv("MILVUS_DRUG_COLLECTION_NAME", "drug_knowledge")
        self.embedding_model = os.getenv("MILVUS_EMBEDDING_MODEL", "bge-m3")
        self.device = os.getenv("EMBEDDING_DEVICE", "cpu")
        
        # Azure OpenAI configuration for embeddings
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_region = os.getenv("AZURE_OPENAI_REGION", "eastus")
        self.model_name = os.getenv("MODEL_NAME", "text-embedding-3-large")
        self.deployment = os.getenv("DEPLOYMENT", "text-embedding-3-large")
        self.api_version = os.getenv("API_VERSION", "2024-02-01")
        
        self.connected = False
        self.collection = None
        self.drug_collection = None
        
        # Check if configuration is available
        if not self.uri or not self.token:
            logger.warning("Zilliz/Milvus configuration not found. Vector store will not be available.")
            logger.warning("Please set MILVUS_URI and MILVUS_TOKEN environment variables.")
            return
        
        try:
            self._connect()
        except Exception as e:
            logger.error(f"Failed to connect to Zilliz/Milvus: {e}")
    
    def _connect(self):
        """Connect to Zilliz Cloud."""
        try:
            connections.connect(
                alias="default",
                uri=self.uri,
                token=self.token,
                db_name=self.db_name
            )
            self.connected = True
            logger.info(f"Connected to Zilliz Cloud database: {self.db_name}")
            
            # Load collections
            self._load_collections()
            
        except Exception as e:
            logger.error(f"Failed to connect to Zilliz Cloud: {e}")
            self.connected = False
            raise
    
    def _load_collections(self):
        """Load and verify collections."""
        try:
            # Check if medical knowledge collection exists
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                self.collection.load()
                logger.info(f"Loaded collection: {self.collection_name}")
            else:
                logger.warning(f"Collection '{self.collection_name}' not found")
            
            # Check if drug collection exists
            if utility.has_collection(self.drug_collection_name):
                self.drug_collection = Collection(self.drug_collection_name)
                self.drug_collection.load()
                logger.info(f"Loaded collection: {self.drug_collection_name}")
            else:
                logger.warning(f"Collection '{self.drug_collection_name}' not found")
                
        except Exception as e:
            logger.error(f"Failed to load collections: {e}")
            raise
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using Azure OpenAI."""
        if not self.azure_api_key or not self.azure_endpoint:
            logger.warning("Azure OpenAI configuration not found. Cannot generate embeddings.")
            return []
        
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": self.azure_api_key
            }
            
            data = {
                "input": text,
                "model": self.model_name
            }
            
            response = requests.post(
                f"{self.azure_endpoint}/openai/deployments/{self.deployment}/embeddings?api-version={self.api_version}",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["data"][0]["embedding"]
            else:
                logger.error(f"Azure OpenAI embedding request failed: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []
    
    def search_medical_knowledge(self, query: str, k: int = 8) -> Tuple[str, List[str]]:
        """
        Search medical knowledge collection.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            Tuple of (context_text, source_list)
        """
        if not self.connected or not self.collection:
            logger.warning("Zilliz service not connected or collection not available")
            return "No vector store available - using AI without RAG context", []
        
        try:
            # Get embedding for query
            query_embedding = self._get_embedding(query)
            if not query_embedding:
                logger.warning("Failed to get query embedding")
                return "Failed to generate query embedding", []
            
            # Search collection
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=k,
                output_fields=["text", "source", "metadata"]
            )
            
            # Process results
            context_parts = []
            sources = []
            
            for hits in results:
                for hit in hits:
                    text = hit.entity.get("text", "")
                    source = hit.entity.get("source", "Unknown")
                    metadata = hit.entity.get("metadata", {})
                    
                    if text:
                        context_parts.append(text)
                        sources.append(source)
            
            context_text = "\n\n".join(context_parts) if context_parts else "No relevant medical knowledge found"
            
            logger.info(f"Retrieved {len(context_parts)} medical knowledge entries")
            return context_text, sources
            
        except Exception as e:
            logger.error(f"Error searching medical knowledge: {e}")
            return f"Error searching medical knowledge: {str(e)}", []
    
    def search_drug_knowledge(self, query: str, k: int = 5) -> Tuple[str, List[str]]:
        """
        Search drug knowledge collection.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            Tuple of (context_text, source_list)
        """
        if not self.connected or not self.drug_collection:
            logger.warning("Zilliz service not connected or drug collection not available")
            return "No drug database available", []
        
        try:
            # Get embedding for query
            query_embedding = self._get_embedding(query)
            if not query_embedding:
                logger.warning("Failed to get query embedding for drug search")
                return "Failed to generate query embedding", []
            
            # Search collection
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            results = self.drug_collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=k,
                output_fields=["drug_name", "description", "indications", "contraindications", "dosage", "side_effects"]
            )
            
            # Process results
            drug_info_parts = []
            sources = []
            
            for hits in results:
                for hit in hits:
                    drug_name = hit.entity.get("drug_name", "")
                    description = hit.entity.get("description", "")
                    indications = hit.entity.get("indications", "")
                    contraindications = hit.entity.get("contraindications", "")
                    dosage = hit.entity.get("dosage", "")
                    side_effects = hit.entity.get("side_effects", "")
                    
                    if drug_name:
                        drug_info = f"Drug: {drug_name}\n"
                        if description:
                            drug_info += f"Description: {description}\n"
                        if indications:
                            drug_info += f"Indications: {indications}\n"
                        if contraindications:
                            drug_info += f"Contraindications: {contraindications}\n"
                        if dosage:
                            drug_info += f"Dosage: {dosage}\n"
                        if side_effects:
                            drug_info += f"Side Effects: {side_effects}\n"
                        
                        drug_info_parts.append(drug_info)
                        sources.append(f"Drug Database - {drug_name}")
            
            context_text = "\n\n".join(drug_info_parts) if drug_info_parts else "No relevant drug information found"
            
            logger.info(f"Retrieved {len(drug_info_parts)} drug entries")
            return context_text, sources
            
        except Exception as e:
            logger.error(f"Error searching drug knowledge: {e}")
            return f"Error searching drug knowledge: {str(e)}", []
    
    def search_all_collections(self, query: str, patient_data: str, k: int = 8) -> Tuple[str, List[str]]:
        """
        Search both medical knowledge and drug collections.
        
        Args:
            query: Search query
            patient_data: Patient data for context
            k: Number of results to return
            
        Returns:
            Tuple of (combined_context_text, source_list)
        """
        if not self.connected:
            logger.warning("Zilliz service not connected")
            return "No vector store available - using AI without RAG context", []
        
        # Combine query and patient data for richer context
        full_query = f"{query}\n{patient_data}".strip()
        
        # Search medical knowledge
        medical_context, medical_sources = self.search_medical_knowledge(full_query, k)
        
        # Search drug knowledge
        drug_context, drug_sources = self.search_drug_knowledge(full_query, k//2)
        
        # Combine results
        all_contexts = []
        all_sources = []
        
        if medical_context and medical_context != "No relevant medical knowledge found":
            all_contexts.append(f"MEDICAL KNOWLEDGE:\n{medical_context}")
            all_sources.extend(medical_sources)
        
        if drug_context and drug_context != "No relevant drug information found":
            all_contexts.append(f"DRUG INFORMATION:\n{drug_context}")
            all_sources.extend(drug_sources)
        
        combined_context = "\n\n".join(all_contexts) if all_contexts else "No relevant medical or drug information found"
        
        logger.info(f"Combined search returned {len(all_sources)} sources")
        return combined_context, all_sources
    
    def load_collection(self):
        """Load collections (for compatibility with vectorstore_manager)."""
        try:
            if not self.connected:
                self._connect()
            return True
        except Exception as e:
            logger.error(f"Failed to load collections: {e}")
            return False


# Global service instance
vectordb_service = ZillizService()
