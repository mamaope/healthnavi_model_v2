"""
Modular Conversational Service for HealthNavi AI CDSS.

This module provides a clean, modular conversational service with configurable
components for prompts, models, classification, and response processing.
"""

import os
import time
import logging
from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass

from fastapi import HTTPException
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.api_core import exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
import vertexai

from healthnavi.core.config import get_config
from healthnavi.core.ai_config import (
    AIConfig, QueryType, ModelConfig, PromptConfig, ClassificationRule,
    get_ai_config_manager, get_ai_config
)
from healthnavi.core.security import SecureLogger, InputValidator
from healthnavi.services.vectorstore_manager import search_all_collections

config = get_config()
ai_config_manager = get_ai_config_manager()
logger = logging.getLogger(__name__)

# Initialize security components
secure_logger = SecureLogger()
input_validator = InputValidator()


@dataclass
class ConversationRequest:
    """Request for conversational AI processing."""
    query: str
    chat_history: str
    patient_data: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    custom_config: Optional[Dict[str, Any]] = None


@dataclass
class ConversationResponse:
    """Response from conversational AI processing."""
    response_text: str
    diagnosis_complete: bool
    query_type: QueryType
    confidence_score: float
    processing_metadata: Dict[str, Any]
    validation_result: Optional[Dict[str, Any]] = None


class QueryClassifier:
    """Simple query classifier based on keyword matching."""
    
    def __init__(self, classification_rules: List[ClassificationRule]):
        self.rules = sorted(classification_rules, key=lambda r: r.priority)
    
    def classify_query(self, query: str) -> Tuple[QueryType, float]:
        """Classify a query based on keywords."""
        query_lower = query.lower()
        
        for rule in self.rules:
            keyword_matches = sum(1 for keyword in rule.keywords if keyword in query_lower)
            if keyword_matches > 0:
                confidence = min(keyword_matches / len(rule.keywords), 1.0)
                if confidence >= rule.confidence_threshold:
                    return rule.query_type, confidence
        
        # Default to general query
        return QueryType.GENERAL_QUERY, 0.5


class PromptManager:
    """Manages prompt templates and variable substitution."""
    
    def __init__(self, prompts: Dict[QueryType, PromptConfig]):
        self.prompts = prompts
    
    def get_prompt(self, query_type: QueryType, variables: Dict[str, str]) -> str:
        """Get formatted prompt for a query type."""
        prompt_config = self.prompts.get(query_type)
        if not prompt_config:
            raise ValueError(f"No prompt configuration found for {query_type}")
        
        try:
            return prompt_config.template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing required variable for prompt: {e}")
    
    def validate_prompt_length(self, prompt: str, query_type: QueryType) -> bool:
        """Validate prompt length."""
        prompt_config = self.prompts.get(query_type)
        if not prompt_config:
            return False
        
        return len(prompt) <= prompt_config.max_length


class ModelManager:
    """Manages AI model interactions."""
    
    def __init__(self, models: Dict[str, ModelConfig], default_model: str):
        self.models = models
        self.default_model = default_model
        self._initialize_vertex_ai()
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI."""
        try:
            vertexai.init(
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION")
            )
            logger.info("Vertex AI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise HTTPException(status_code=500, detail="AI service initialization failed")
    
    def generate_response(self, prompt: str, model_name: Optional[str] = None) -> str:
        """Generate response using the specified model."""
        model_name = model_name or self.default_model
        model_config = self.models.get(model_name)
        
        if not model_config:
            raise ValueError(f"Model configuration not found: {model_name}")
        
        if model_config.provider.value != "vertex_ai":
            raise ValueError(f"Only Vertex AI models are currently supported")
        
        return self._generate_with_vertex_ai(prompt, model_config)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_not_exception_type((HTTPException, ValueError))
    )
    def _generate_with_vertex_ai(self, prompt: str, model_config: ModelConfig) -> str:
        """Generate response using Vertex AI."""
        try:
            model = GenerativeModel(model_config.model_name)
            
            generation_config = GenerationConfig(
                max_output_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
                top_p=model_config.top_p,
                top_k=model_config.top_k
            )
            
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=model_config.safety_settings
            )
            
            if not response.text:
                raise HTTPException(status_code=500, detail="Empty response from AI model")
            
            return response.text.strip()
            
        except exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}")
            raise HTTPException(status_code=500, detail="AI service temporarily unavailable")
        except Exception as e:
            logger.error(f"Unexpected error in AI generation: {e}")
            raise HTTPException(status_code=500, detail="AI generation failed")


class ResponseProcessor:
    """Processes and validates AI responses."""
    
    def __init__(self):
        self.secure_logger = SecureLogger()
    
    def process_response(self, response: str, query_type: QueryType) -> Dict[str, Any]:
        """Process and validate AI response."""
        # Basic validation
        if not response or len(response.strip()) < 10:
            raise ValueError("Response too short or empty")
        
        # Check for medical disclaimer
        has_disclaimer = any(phrase in response.lower() for phrase in [
            "clinical decision support",
            "not a substitute for professional medical advice",
            "consult with a healthcare professional"
        ])
        
        # Determine if diagnosis is complete
        diagnosis_complete = self._is_diagnosis_complete(response, query_type)
        
        return {
            "response_text": response,
            "diagnosis_complete": diagnosis_complete,
            "has_disclaimer": has_disclaimer,
            "response_length": len(response),
            "processing_timestamp": time.time()
        }
    
    def _is_diagnosis_complete(self, response: str, query_type: QueryType) -> bool:
        """Determine if the diagnosis appears complete."""
        if query_type != QueryType.DIFFERENTIAL_DIAGNOSIS:
            return True
        
        # Check for key elements in differential diagnosis
        required_elements = [
            "differential", "diagnosis", "most likely", "recommendations"
        ]
        
        response_lower = response.lower()
        found_elements = sum(1 for element in required_elements if element in response_lower)
        
        return found_elements >= 3


class ModularConversationalService:
    """Main conversational service with modular components."""
    
    def __init__(self):
        self.ai_config = get_ai_config()
        self.classifier = QueryClassifier(self.ai_config.classification_rules)
        self.prompt_manager = PromptManager(self.ai_config.prompts)
        self.model_manager = ModelManager(self.ai_config.models, self.ai_config.default_model)
        self.response_processor = ResponseProcessor()
    
    async def process_conversation(self, request: ConversationRequest) -> ConversationResponse:
        """Process a conversation request."""
        start_time = time.time()
        
        try:
            # Validate input
            self._validate_request(request)
            
            # Classify query
            query_type, confidence = self.classifier.classify_query(request.query)
            
            # Get relevant context from vector store
            context = await self._get_context(request.query, query_type)
            
            # Prepare prompt variables
            prompt_variables = {
                "query": request.query,
                "patient_data": request.patient_data,
                "chat_history": request.chat_history,
                "context": context,
                "sources": self._format_sources(context)
            }
            
            # Get formatted prompt
            prompt = self.prompt_manager.get_prompt(query_type, prompt_variables)
            
            # Validate prompt length
            if not self.prompt_manager.validate_prompt_length(prompt, query_type):
                raise ValueError("Prompt too long for processing")
            
            # Generate response
            response_text = self.model_manager.generate_response(prompt)
            
            # Process response
            processing_result = self.response_processor.process_response(response_text, query_type)
            
            # Prepare metadata
            processing_metadata = {
                "query_type": query_type.value,
                "confidence_score": confidence,
                "processing_time": time.time() - start_time,
                "model_used": self.ai_config.default_model,
                "context_length": len(context),
                "prompt_length": len(prompt),
                **processing_result
            }
            
            return ConversationResponse(
                response_text=processing_result["response_text"],
                diagnosis_complete=processing_result["diagnosis_complete"],
                query_type=query_type,
                confidence_score=confidence,
                processing_metadata=processing_metadata
            )
            
        except Exception as e:
            logger.error(f"Error processing conversation: {e}")
            raise HTTPException(status_code=500, detail=f"Conversation processing failed: {str(e)}")
    
    def _validate_request(self, request: ConversationRequest) -> None:
        """Validate conversation request."""
        if not request.query or len(request.query.strip()) < 3:
            raise ValueError("Query must be at least 3 characters long")
        
        # Use the correct validation method
        query_validation = input_validator.validate_patient_data(request.query)
        if not query_validation['is_valid']:
            raise ValueError(f"Query validation failed: {query_validation['error']}")
        
        if request.patient_data:
            patient_validation = input_validator.validate_patient_data(request.patient_data)
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
    
    def _format_sources(self, context: str) -> str:
        """Extract and format sources from context."""
        if not context or context == "No relevant context found." or context == "Context retrieval failed.":
            return "No sources available"
        
        # Extract sources from context (this is a simple implementation)
        # In a more sophisticated system, you'd parse the actual source metadata
        sources = []
        lines = context.split('\n')
        for line in lines:
            if 'Source:' in line or 'source:' in line:
                sources.append(line.strip())
        
        if sources:
            return '\n'.join(sources)
        else:
            return "Medical knowledge base"


# Global service instance
_conversational_service: Optional[ModularConversationalService] = None


def get_conversational_service() -> ModularConversationalService:
    """Get the global conversational service instance."""
    global _conversational_service
    if _conversational_service is None:
        _conversational_service = ModularConversationalService()
    return _conversational_service


async def generate_response(
    query: str,
    chat_history: str = "",
    patient_data: str = "",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> Tuple[str, bool]:
    """
    Generate AI response for diagnosis queries.
    
    Args:
        query: The user's query
        chat_history: Previous conversation history
        patient_data: Patient information
        user_id: User identifier
        session_id: Session identifier
    
    Returns:
        Tuple of (response_text, diagnosis_complete)
    """
    service = get_conversational_service()
    
    request = ConversationRequest(
        query=query,
        chat_history=chat_history,
        patient_data=patient_data,
        user_id=user_id,
        session_id=session_id
    )
    
    response = await service.process_conversation(request)
    
    return response.response_text, response.diagnosis_complete
