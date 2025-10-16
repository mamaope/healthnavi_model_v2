"""
Enhanced conversational service for HealthNavi AI CDSS.

This module provides secure AI conversation handling with proper validation,
audit logging, and data protection following medical software standards.
"""

import os
import json
import asyncio
import time
import logging
import re
from typing import Dict, Tuple, List, Optional, Any
from enum import Enum
from fastapi import HTTPException
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.api_core import exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
import vertexai

from healthnavi.core.config import get_config
from healthnavi.core.security import SecureLogger, InputValidator, EncryptionService
from healthnavi.services.vectorstore_manager import search_all_collections
from healthnavi.services.model_config import get_model_manager

config = get_config()
logger = logging.getLogger(__name__)

# Initialize encryption service
encryption_service = EncryptionService()


class QueryType(Enum):
    """Query type enumeration."""
    DRUG_INFORMATION = "drug_information"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    GENERAL_QUERY = "general_query"


class PromptTemplates:
    """Secure prompt templates for different query types."""
    
    GENERAL_PROMPT = """
You are an expert medical AI, assisting a qualified doctor. Your task is to analyze patient information and generate a structured clinical assessment based ONLY on the provided reference materials.

IMPORTANT: You must follow all rules listed below.

---
RULES:
1. **Source of Truth**: Base your analysis strictly on the `REFERENCE TEXT TO USE`. Do NOT introduce external knowledge or sources.
2. **Citations**: Cite only when:
   - Quoting or paraphrasing specific guidelines, diagnostic criteria, or treatment protocols  
   - Recommending diagnostic tests, treatments, or management approaches based on reference material  
   Do NOT cite for general background knowledge, physiology, or obvious clinical observations.
3. **Citation Format**: Use only the exact names from `AVAILABLE KNOWLEDGE BASE SOURCES`. Include page numbers, section titles, or identifiers if available, in the format: `[Source: document_name, page/section]`. Never invent or approximate sources.
4. **Critical Safety First**: If vital signs or findings suggest immediate danger, begin your response with a **CRITICAL ALERT 🚨** section (before all other sections), highlighting the urgent issue and necessary emergency steps.
5. **Probabilities**: Assign probability percentages (0–100%) for each diagnosis in the differential. Distribute probabilities realistically (they should sum to ~100% unless case data is incomplete).
6. **Medical Acronyms**: Expand and correctly interpret all acronyms on first use, then use them consistently.
7. **Output Format**: Always follow this structure, in markdown with clear section headers and bullet lists:
   - **CLINICAL OVERVIEW**  
   - **DIFFERENTIAL DIAGNOSES**  
   - **IMMEDIATE WORKUP & INVESTIGATIONS**  
   - **MANAGEMENT & RECOMMENDATIONS**  
   - **RED FLAGS / DANGER SIGNS**  
   - **ADDITIONAL INFORMATION NEEDED** (include only if applicable)  
   - **Sources**
8. **Conciseness**: Be direct, factual, and free of filler language. Write as if documenting in a clinical record.
9. **Information Gaps**: If insufficient data prevents forming a reliable differential, state this clearly and request the single most critical missing detail in the "ADDITIONAL INFORMATION NEEDED" section.
10. **Non-Medical Cases**: If the case is not primarily medical (e.g., social or psychological), state this and suggest appropriate non-medical resources.

---
**CRITICAL FORMATTING RULES - MUST FOLLOW:**
- ALWAYS put a BLANK LINE (press ENTER twice) after each **HEADING**
- ALWAYS put a BLANK LINE before starting a new **HEADING**
- Each list item (1. 2. 3. or -) must be on its OWN separate line
- NEVER write content on the same line as the heading
- Pattern: **HEADING**[ENTER][ENTER]Content starts here[ENTER][ENTER]**NEXT HEADING**

---
**EXAMPLE FORMAT (FOLLOW EXACTLY):**

**CLINICAL OVERVIEW**

[1–2 paragraph summary of the case, highlighting key clinical features and initial impression]

**DIFFERENTIAL DIAGNOSES**

1. **[Primary Diagnosis]** (XX%): [Brief justification with supporting/opposing evidence; cite only if guideline/protocol reference is used]

2. **[Secondary Diagnosis]** (XX%): [Justification]

3. **[Tertiary Diagnosis]** (XX%): [Justification]

[Add additional diagnoses if clinically relevant]

**IMMEDIATE WORKUP & INVESTIGATIONS**

- [Essential test 1]

- [Essential test 2]

- [Essential test 3]

[Include time-sensitive protocols if relevant]

**MANAGEMENT & RECOMMENDATIONS**

- [Immediate/urgent management step]

- [Evidence-based treatment recommendation]

- [Monitoring requirements and follow-up]

**RED FLAGS / DANGER SIGNS**

- [Warning sign 1 needing urgent escalation]

- [Warning sign 2]

**ADDITIONAL INFORMATION NEEDED**

[One critical, focused question to refine diagnosis/management - only if applicable]

**Sources**

{sources}

---

REFERENCE TEXT TO USE:  
{context}

AVAILABLE KNOWLEDGE BASE SOURCES:  
{sources}

PATIENT'S CURRENT INFORMATION:  
{patient_data}

PREVIOUS CONVERSATION:  
{chat_history}

YOUR TASK:  
Generate the structured assessment according to the rules. Focus on practical, clinically actionable guidance. Cite only when pulling directly from the provided knowledge base. Never invent or hallucinate content.

**CRITICAL FORMATTING RULES - MUST FOLLOW:**
- ALWAYS put a BLANK LINE (press ENTER twice) after each **HEADING**
- ALWAYS put a BLANK LINE before starting a new **HEADING**
- Each list item (1. 2. 3. or -) must be on its OWN separate line
- NEVER write content on the same line as the heading
- Pattern: **HEADING**[ENTER][ENTER]Content starts here[ENTER][ENTER]**NEXT HEADING**
"""

    # Legacy prompts for backward compatibility (now all use GENERAL_PROMPT)
    DIFFERENTIAL_DIAGNOSIS_PROMPT = GENERAL_PROMPT
    DRUG_INFORMATION_PROMPT = GENERAL_PROMPT
    CLINICAL_GUIDANCE_PROMPT = GENERAL_PROMPT


class ConversationalService:
    """Enhanced conversational service with security and medical compliance."""
    
    def __init__(self):
        """Initialize the conversational service."""
        self.model = None
        self.secure_logger = SecureLogger()
        self.input_validator = InputValidator()
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize the Vertex AI model."""
        try:
            # Get model configuration
            model_config = get_model_manager().get_vertex_ai_config()
            project_id = model_config.get("project")
            location = model_config.get("location", "us-central1")

            # Initialize Vertex AI
            vertexai.init(project=project_id, location=location)
            
            # Create the model
            self.model = GenerativeModel(
                model_name="gemini-2.5-flash",
                generation_config=GenerationConfig(
                    temperature=0.2,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=3000,
                    candidate_count=1,
                )
            )
            
            logger.info("ConversationalService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ConversationalService: {e}")

            # Provide more specific error messages for common issues
            error_message = str(e).lower()
            if "credentials" in error_message or "authentication" in error_message:
                detail = "Google Cloud credentials not configured. Please set GOOGLE_APPLICATION_CREDENTIALS environment variable."
            elif "project" in error_message:
                detail = "Google Cloud project not configured. Please set GOOGLE_CLOUD_PROJECT environment variable."
            elif "permission" in error_message or "forbidden" in error_message:
                detail = "Insufficient permissions for Vertex AI. Check your service account credentials and permissions."
            else:
                detail = f"AI service initialization failed: {str(e)}. Please check your Google Cloud configuration."

            raise HTTPException(
                status_code=503,
                detail=detail
            )
    
    def _get_prompt_template(self, query_type: QueryType) -> str:
        """Get appropriate prompt template for query type."""
        if query_type == QueryType.DRUG_INFORMATION:
            return PromptTemplates.DRUG_INFORMATION_PROMPT
        elif query_type == QueryType.DIFFERENTIAL_DIAGNOSIS:
            return PromptTemplates.DIFFERENTIAL_DIAGNOSIS_PROMPT
        else:
            return PromptTemplates.GENERAL_PROMPT
    
    def _get_temperature_setting(self, query_type: QueryType) -> float:
        """Get appropriate temperature setting for query type."""
        if query_type == QueryType.DRUG_INFORMATION:
            return 0.2  # Lower temperature for factual drug information
        elif query_type == QueryType.DIFFERENTIAL_DIAGNOSIS:
            return 0.3  # Moderate temperature for clinical reasoning
        else:
            return 0.3  # Default for general queries

    def _determine_query_type(self, query: str) -> QueryType:
        """Determine the type of query."""
        query_lower = query.lower()

        # Drug-related queries
        drug_keywords = ['drug', 'medication', 'medicine', 'pharmacy', 'pharmacology', 'side effect', 'interaction', 'contraindication', 'dosage', 'prescription']
        if any(keyword in query_lower for keyword in drug_keywords):
            return QueryType.DRUG_INFORMATION

        # Diagnosis-related queries
        diagnosis_keywords = ['diagnosis', 'differential', 'symptom', 'patient', 'clinical', 'sign', 'history', 'examination', 'assessment']
        if any(keyword in query_lower for keyword in diagnosis_keywords):
            return QueryType.DIFFERENTIAL_DIAGNOSIS

        return QueryType.GENERAL_QUERY

    def _format_prompt(self, prompt_template: str, query: str, context: str, sources: str, chat_history: str = "", patient_data: str = "") -> str:
        """Format the prompt with provided variables."""
        try:
            # Clean and validate inputs
            query = self.input_validator.validate_query(query)
            context = self.input_validator.validate_context(context)
            sources = self.input_validator.validate_sources(sources)

            # Format the prompt
            formatted_prompt = prompt_template.format(
                query=query,
                context=context,
                sources=sources,
                chat_history=chat_history,
                patient_data=patient_data
            )

            # Log prompt for debugging (without sensitive data)
            logger.debug(f"Formatted prompt length: {len(formatted_prompt)}")

            return formatted_prompt

        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            raise HTTPException(
                status_code=400,
                detail="Invalid input data for prompt formatting"
            )

    async def generate_response(self, query: str, chat_history: str, patient_data: str) -> Tuple[str, bool, str]:
        """Generate AI response for the given query.
        
        Args:
            query: User query
            chat_history: Previous conversation history
            patient_data: Patient data
            
        Returns:
            Tuple of (response_text, diagnosis_complete, prompt_type)
        """
        start_time = time.time()
        
        try:
            # Log the request (without sensitive data)
            self.secure_logger.log_request(
                action="generate_response",
                details={
                    "query_length": len(query),
                    "patient_data_length": len(patient_data),
                    "chat_history_length": len(chat_history)
                }
            )

            # Determine query type
            query_type = self._determine_query_type(query)

            # Get context from vector database
            context_data, sources = await self._get_context_and_sources(query, patient_data)

            # Get appropriate prompt template
            prompt_template = self._get_prompt_template(query_type)

            # Format the prompt
            formatted_prompt = self._format_prompt(
                prompt_template, query, context_data, sources, chat_history, patient_data
            )

            # Generate response using Vertex AI
            response = await self._generate_with_vertex_ai(formatted_prompt, query_type)

            # Process and validate response
            processed_response, diagnosis_complete = self._process_response(response, query_type)

            # Log successful response
            execution_time = time.time() - start_time
            self.secure_logger.log_request(
                action="generate_response_success",
                details={
                    "execution_time": execution_time,
                    "response_length": len(processed_response),
                    "query_type": query_type.value
                }
            )

            logger.info(f"Response generated successfully in {execution_time:.2f}s")

            return processed_response, diagnosis_complete, query_type.value

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error generating response after {execution_time:.2f}s: {e}")

            # Log error securely
            self.secure_logger.log_request(
                action="generate_response_error",
                details={"error": str(e), "execution_time": execution_time}
            )

            # Re-raise with sanitized error message
            raise HTTPException(
                status_code=503,
                detail="AI service is currently unavailable. Please try again later."
            )

    async def _get_context_and_sources(self, query: str, patient_data: str) -> Tuple[str, str]:
        """Get context and sources from vector database."""
        try:
            # Search vector database for relevant context
            context_results = await search_all_collections(query, patient_data)

            # Format context from results
            context_parts = []
            sources_list = []

            for result in context_results:
                if result.get("content"):
                    context_parts.append(f"**Source: {result.get('source', 'Unknown')}**\n{result['content']}")
                    sources_list.append(result.get('source', 'Unknown'))

            context = "\n\n".join(context_parts) if context_parts else "No relevant context found in knowledge base."
            sources = ", ".join(sources_list) if sources_list else "General medical knowledge"

            return context, sources

        except Exception as e:
            logger.warning(f"Error getting context from vector database: {e}")
            return "Context retrieval failed. Using general medical knowledge.", "General medical knowledge"

    async def _generate_with_vertex_ai(self, prompt: str, query_type: QueryType) -> str:
        """Generate response using Vertex AI."""
        if not self.model:
            raise HTTPException(status_code=503, detail="AI model not initialized")

        try:
            # Set temperature based on query type
            temperature = self._get_temperature_setting(query_type)

            # Update model configuration
            self.model._generation_config = GenerationConfig(
                temperature=temperature,
                top_p=0.95,
                top_k=40,
                max_output_tokens=4096,
            )

            # Generate response
            response = self.model.generate_content(prompt)

            if response and response.text:
                return response.text.strip()
            else:
                raise Exception("Empty response from AI model")

        except exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}")
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable due to API error"
            )
        except Exception as e:
            logger.error(f"Error generating response with Vertex AI: {e}")
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable"
            )

    def _process_response(self, response: str, query_type: QueryType) -> Tuple[str, bool]:
        """Process and validate the AI response."""
        try:
            # Clean and validate response
            cleaned_response = self.input_validator.validate_response(response)

            # Check if diagnosis is complete (for differential diagnosis queries)
            diagnosis_complete = self._check_diagnosis_completion(cleaned_response, query_type)

            # Log response processing
            logger.debug(f"Processed response length: {len(cleaned_response)}")

            return cleaned_response, diagnosis_complete

        except Exception as e:
            logger.error(f"Error processing response: {e}")
            raise HTTPException(
                status_code=503,
                detail="Error processing AI response"
            )

    def _check_diagnosis_completion(self, response: str, query_type: QueryType) -> bool:
        """Check if the diagnosis response is complete."""
        if query_type != QueryType.DIFFERENTIAL_DIAGNOSIS:
            return True

        # For differential diagnosis, check if we have sufficient information
        required_sections = ["differential", "management", "investigation"]
        response_lower = response.lower()

        # Count how many required sections are present
        found_sections = sum(1 for section in required_sections if section in response_lower)

        # Consider complete if at least 2 out of 3 sections are present
        return found_sections >= 2


# Global conversational service instance
_conversational_service: Optional[ConversationalService] = None


def get_conversational_service() -> ConversationalService:
    """Get the global conversational service instance."""
    global _conversational_service
    if _conversational_service is None:
        _conversational_service = ConversationalService()
    return _conversational_service


async def generate_response(query: str, chat_history: str, patient_data: str) -> Tuple[str, bool, str]:
    """Generate AI response for the given query.
    
    Args:
        query: User query
        chat_history: Previous conversation history
        patient_data: Patient data
        
    Returns:
        Tuple of (response_text, diagnosis_complete, prompt_type)
    """
    return await get_conversational_service().generate_response(query, chat_history, patient_data)