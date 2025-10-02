"""
Modular Conversational Service for HealthNavi AI CDSS.

This service orchestrates the modular components for AI conversations.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import vertexai
from vertexai.generative_models import GenerativeModel, Part

from .prompt_manager import get_prompt_manager, QueryType
from .model_config import get_model_manager
from .query_classifier import get_query_classifier
from .response_processor import get_response_processor
from ..core.security import InputValidator
from ..services.vectorstore_manager import search_all_collections

logger = logging.getLogger(__name__)


@dataclass
class ConversationRequest:
    """Request for conversation processing."""
    query: str
    chat_history: str
    patient_data: str
    user_id: str
    session_id: Optional[str] = None


@dataclass
class ConversationResponse:
    """Response from conversation processing."""
    content: str
    query_type: str
    confidence: float
    sources: List[str]
    metadata: Dict[str, Any]
    is_json_format: bool


class ModularConversationalService:
    """Modular conversational service using separate components."""
    
    def __init__(self):
        """Initialize the modular conversational service."""
        self.prompt_manager = get_prompt_manager()
        self.model_manager = get_model_manager()
        self.query_classifier = get_query_classifier()
        self.response_processor = get_response_processor()
        self.input_validator = InputValidator()
        
        # Initialize Vertex AI
        self._initialize_vertex_ai()
        
        logger.info("Modular conversational service initialized")
    
    def _initialize_vertex_ai(self) -> None:
        """Initialize Vertex AI."""
        try:
            vertex_ai_config = self.model_manager.get_vertex_ai_config()
            
            if not vertex_ai_config["project"] or not vertex_ai_config["location"]:
                logger.warning("Vertex AI configuration incomplete, using defaults")
                vertex_ai_config["project"] = os.getenv("GOOGLE_CLOUD_PROJECT", "regal-autonomy-454806-d1")
                vertex_ai_config["location"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            
            vertexai.init(
                project=vertex_ai_config["project"],
                location=vertex_ai_config["location"]
            )
            logger.info("Vertex AI initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise
    
    async def process_conversation(self, request: ConversationRequest) -> ConversationResponse:
        """Process a conversation request."""
        try:
            # Validate input
            self._validate_request(request)
            
            # Classify query
            query_type, confidence = self.query_classifier.classify_query(
                request.query, request.patient_data
            )
            
            logger.info(f"Query classified as {query_type} with confidence {confidence}")
            
            # Get context from vector store
            context = await self._get_context(request.query, query_type)
            
            # Get prompt template
            prompt_template = self.prompt_manager.get_prompt_template(query_type)
            prompt_variables = self.prompt_manager.get_prompt_variables(query_type)
            
            if not prompt_template:
                raise ValueError(f"No prompt template found for {query_type}")
            
            # Prepare prompt variables
            prompt_vars = self._prepare_prompt_variables(
                request, context, prompt_variables
            )
            
            # Format prompt
            formatted_prompt = self._format_prompt(prompt_template, prompt_vars)
            
            # Get model configuration
            model_config = self.model_manager.get_default_model()
            
            # Generate response
            raw_response = await self._generate_response(formatted_prompt, model_config)
            
            # Log raw response for debugging
            logger.info(f"Raw AI response length: {len(raw_response)} characters")
            logger.info(f"Raw response preview: {raw_response[:200]}...")
            
            # Process response
            processed_response = self.response_processor.process_response(
                raw_response, query_type.value
            )
            
            # Log processed response details
            logger.info(f"Processed response format: {processed_response.format_type}")
            logger.info(f"Processed response valid: {processed_response.is_valid}")
            if processed_response.format_type == "json":
                logger.info(f"JSON response metadata: {processed_response.metadata}")
            
            # Extract sources
            sources = self.response_processor.extract_sources(raw_response)
            
            # Validate response
            validation = self.response_processor.validate_response(
                raw_response, query_type.value
            )
            
            # Ensure JSON response is properly formatted
            final_content = processed_response.content
            if processed_response.format_type == "json" and processed_response.is_valid:
                # Validate JSON is properly formatted
                try:
                    json.loads(final_content)
                    logger.info("JSON response validation successful")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON validation failed: {e}")
                    # Try extracting JSON from markdown code blocks
                    from healthnavi.services.response_processor import get_response_processor
                    processor = get_response_processor()
                    json_content = processor._extract_json_from_markdown(raw_response)
                    if json_content:
                        try:
                            json.loads(json_content)
                            final_content = json_content
                            logger.info("Successfully extracted JSON from markdown code blocks")
                        except json.JSONDecodeError:
                            logger.error("Failed to extract valid JSON from markdown")
                            final_content = raw_response
                            processed_response.format_type = "text"
                    else:
                        # Fallback to text format
                        final_content = raw_response
                        processed_response.format_type = "text"
            
            return ConversationResponse(
                content=final_content,
                query_type=query_type.value,
                confidence=confidence,
                sources=sources,
                metadata={
                    "validation": validation,
                    "prompt_length": len(formatted_prompt),
                    "response_length": len(raw_response),
                    "is_json_format": processed_response.format_type == "json",
                    "json_metadata": processed_response.metadata if processed_response.format_type == "json" else None
                },
                is_json_format=processed_response.format_type == "json"
            )
        
        except Exception as e:
            logger.error(f"Error processing conversation: {e}")
            raise
    
    def _validate_request(self, request: ConversationRequest) -> None:
        """Validate conversation request."""
        if not request.query or len(request.query.strip()) < 3:
            raise ValueError("Query must be at least 3 characters long")
        
        # Use input validator
        query_validation = self.input_validator.validate_patient_data(request.query)
        if not query_validation['is_valid']:
            raise ValueError(f"Query validation failed: {query_validation['error']}")
        
        if request.patient_data:
            patient_validation = self.input_validator.validate_patient_data(request.patient_data)
            if not patient_validation['is_valid']:
                raise ValueError(f"Patient data validation failed: {patient_validation['error']}")
    
    async def _get_context(self, query: str, query_type: QueryType) -> str:
        """Get relevant context from vector store."""
        try:
            # Search vector store for relevant information
            search_results = search_all_collections(query, "", k=5)
            
            if not search_results or not search_results[1]:
                return "No relevant context found."
            
            # Format context from search results
            context_parts = []
            for result in search_results[1]:
                context_parts.append(f"Content: {result}")
                context_parts.append("---")
            
            return "\n".join(context_parts)
        
        except Exception as e:
            logger.warning(f"Failed to get context from vector store: {e}")
            return "Context retrieval failed."
    
    def _prepare_prompt_variables(self, request: ConversationRequest, context: str, variables: List[str]) -> Dict[str, str]:
        """Prepare prompt variables."""
        prompt_vars = {}
        
        for var in variables:
            if var == "query":
                prompt_vars[var] = request.query
            elif var == "patient_data":
                prompt_vars[var] = request.patient_data
            elif var == "chat_history":
                prompt_vars[var] = request.chat_history
            elif var == "context":
                prompt_vars[var] = context
            elif var == "sources":
                prompt_vars[var] = self._format_sources(context)
            else:
                prompt_vars[var] = ""
        
        return prompt_vars
    
    def _format_sources(self, context: str) -> str:
        """Extract and format sources from context."""
        if not context or context == "No relevant context found." or context == "Context retrieval failed.":
            return "No sources available"
        
        # Extract sources from context
        sources = []
        lines = context.split('\n')
        for line in lines:
            if 'Source:' in line or 'source:' in line:
                sources.append(line.strip())
        
        if sources:
            return '\n'.join(sources)
        else:
            return "Medical knowledge base"
    
    def _format_prompt(self, template: str, variables: Dict[str, str]) -> str:
        """Format prompt template with variables."""
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.error(f"Missing variable in prompt template: {e}")
            # Fallback to template without formatting
            return template
    
    async def _generate_response(self, prompt: str, model_config) -> str:
        """Generate AI response using the configured model."""
        try:
            # Use Vertex AI Gemini model
            model = GenerativeModel(model_config.model_name)
            
            # Generate response
            response = model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": model_config.max_tokens,
                    "temperature": model_config.temperature,
                    "top_p": model_config.top_p,
                    "top_k": model_config.top_k,
                }
            )
            
            return response.text
        
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    def reload_configuration(self) -> None:
        """Reload all configuration modules."""
        logger.info("Reloading modular configuration...")
        
        # Reload prompt manager
        self.prompt_manager.reload_prompts()
        
        # Reload other components if they have reload methods
        # (Model manager and query classifier are static for now)
        
        logger.info("Modular configuration reloaded")


# Global modular conversational service instance
_modular_service: Optional[ModularConversationalService] = None


def get_modular_conversational_service() -> ModularConversationalService:
    """Get the global modular conversational service instance."""
    global _modular_service
    if _modular_service is None:
        _modular_service = ModularConversationalService()
    return _modular_service


def reload_modular_configuration() -> None:
    """Reload modular configuration."""
    service = get_modular_conversational_service()
    service.reload_configuration()
