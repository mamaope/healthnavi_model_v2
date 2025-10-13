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
    
    DIFFERENTIAL_DIAGNOSIS_PROMPT = """
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

**FINAL REMINDER:** 
- Put BLANK LINE after **EVERY HEADING**
- Put BLANK LINE before **EVERY HEADING**
- Each list item on its own line
- Follow the example format EXACTLY as shown above
"""

    DRUG_INFORMATION_PROMPT = """
You are an expert pharmacology AI, designed to assist qualified healthcare professionals with drug information. Your task is to provide comprehensive drug information based ONLY on the provided reference materials from the drug knowledge base.

IMPORTANT: You must follow all rules listed below.

---
RULES:
1.  **Source of Truth**: Base your entire response strictly on the `REFERENCE TEXT TO USE`. Do NOT make up or infer information not explicitly provided in the knowledge base.
2.  **Accurate Information**: Only provide information that is directly found in the drug database. If specific information is not available, clearly state "Information not available in knowledge base."
3.  **Accurate Citations**: When citing, use ONLY the exact source names from the `AVAILABLE KNOWLEDGE BASE SOURCES` list. For drug database sources, include the full citation with URL when available.
4.  **Drug Names**: Use the exact drug names as they appear in the knowledge base.
5.  **Markdown Format**: CRITICAL - Use proper markdown formatting with line breaks:
   - ALWAYS put each ## heading on its own line
   - ALWAYS put a blank line before and after each ## heading
   - ALWAYS put each list item (- item) on its own separate line
   - ALWAYS put a blank line before and after lists
   - Use ## for main section headings (e.g., ## 💊 Drug Overview)
   - Use ### for subsections if needed
   - Use **bold** for drug names and important terms
   - Use bullet points (- item) for side effects, interactions, and contraindications - ONE PER LINE
   - Use > for important warnings or notes
   - Use tables for structured data when appropriate
   - CRITICAL: Each list item MUST be on a separate line
   - IMPORTANT: Never run headings together - always separate with blank lines
6.  **Output Format**: Structure your response with each list item on a separate line:

## 💊 Drug Overview

[Brief overview of the drug]

## ⚠️ Side Effects

- **Very Common** (>1/10): [list effects]

- **Common** (1/100 to 1/10): [list effects]

- **Uncommon** (1/1,000 to 1/100): [list effects]

## 🔄 Drug Interactions

- Interaction 1

- Interaction 2

## 🚫 Contraindications

- Contraindication 1

- Contraindication 2

## 🧬 Mechanism of Action

[Mechanism description]

## 🧪 Chemical Information

[Chemical details if available]

## 📚 Sources

{sources}

> **Note:** This application is for clinical decision support and should only be used by qualified healthcare professionals.

REMEMBER: Each list item MUST be on its own line with a blank line after it!

**ABSOLUTE FORMATTING REQUIREMENTS (DO NOT VIOLATE):**
- Output heading, then PRESS ENTER TWICE, then write content
- After content, PRESS ENTER TWICE before next heading
- Each bullet point (- item) gets its own line
- After a list ends, PRESS ENTER TWICE before continuing
- Example: ## Drug Interactions[ENTER][ENTER]- Interaction 1[ENTER]- Interaction 2[ENTER][ENTER]## Next Heading
- NEVER write: ## Heading Content on same line
- ALWAYS write: ## Heading[ENTER][ENTER]Content starts here

---

REFERENCE TEXT TO USE:
{context}

AVAILABLE KNOWLEDGE BASE SOURCES:
{sources}

DRUG QUERY:
{patient_data}

PREVIOUS CONVERSATION:
{chat_history}

YOUR TASK:
Provide comprehensive drug information based on the knowledge base. Focus only on factual information from the provided sources. If the requested drug is not found in the knowledge base, clearly state this and suggest verifying the drug name spelling.

FINAL REMINDER: Put BLANK LINES (double line breaks) before and after EVERY ## heading and EVERY list section! Format example:
## Section Title

Content paragraph here.

- List item 1
- List item 2

## Next Section
"""

    GENERAL_PROMPT = """
You are a medical AI assistant. Answer the user's question based ONLY on the provided reference materials from the knowledge base.

IMPORTANT: You must follow these formatting rules:

1. **Opening Context**: Start with 1-2 sentences providing brief context about the medical topic being asked about.

2. **Main Content**: CRITICAL - Organize your response using clear headings with LINE BREAKS:
   - ALWAYS put each ## heading on its own line
   - ALWAYS put a blank line before and after each ## heading
   - ALWAYS put each list item on its own separate line
   - ALWAYS put a blank line before and after each list
   - Use proper markdown headings (## for main sections, ### for subsections)
   - Use bullet points (- item) for lists of symptoms, signs, or recommendations - ONE PER LINE
   - Use numbered lists (1. 2. 3.) for ordered steps or procedures - ONE PER LINE
   - Use **bold** for important medical terms
   - Use > for blockquotes and warnings
   - Be direct and factual - no conversational greetings or filler words
   - CRITICAL: Each list item MUST be on a separate line
   - IMPORTANT: Never run headings together - always separate with blank lines

3. **Example Format** (CRITICAL: Each list item on separate line with blank line after):

## 📋 Overview

[Brief introduction]

## Common Symptoms

- Symptom 1

- Symptom 2

## Treatment Options

1. First-line treatment

2. Alternative options

> **Warning:** Important safety information

REMEMBER: Each list item MUST be on its own line with a blank line after it!

4. **References**: Include specific citations when stating medical facts, guidelines, or recommendations using the format [Source: document_name, page/section]

5. **Warnings**: If discussing serious conditions, use blockquotes (>) for medical warnings.

6. **Knowledge Base Only**: Base your entire response on the provided reference materials.

**ABSOLUTE FORMATTING REQUIREMENTS (DO NOT VIOLATE):**
- Output heading, then PRESS ENTER TWICE, then write content
- After content, PRESS ENTER TWICE before next heading
- Each list item gets its own line
- After a list ends, PRESS ENTER TWICE before continuing
- NEVER write: ## Heading Content on same line
- ALWAYS write: ## Heading[ENTER][ENTER]Content starts here

---

REFERENCE TEXT TO USE:
{context}

AVAILABLE KNOWLEDGE BASE SOURCES:
{sources}

USER'S QUERY:
{patient_data}

PREVIOUS CONVERSATION:
{chat_history}

YOUR TASK:
Answer the user's question following the formatting rules above. Provide factual, well-structured information based solely on the knowledge base sources.

FINAL REMINDER: Put BLANK LINES (double line breaks) before and after EVERY ## heading and EVERY list section!
"""


class QueryClassifier:
    """Secure query classification service."""
    
    @staticmethod
    async def classify_query(query: str, patient_data: str) -> QueryType:
        """
        Classify the query using rules to determine the user's intent.
        
        Args:
            query: User query
            patient_data: Patient data
            
        Returns:
            QueryType: Classified query type
        """
        full_query = f"{query} {patient_data}".lower().strip()
        
        # Rule for drug information
        drug_keywords = [
            "side effects of", "contraindications for", "dosing of", 
            "interactions of", "mechanism of action", "pharmacology"
        ]
        if any(keyword in full_query for keyword in drug_keywords):
            return QueryType.DRUG_INFORMATION
        
        # Rule for differential diagnosis
        diagnosis_keywords = [
            "differential diagnosis", "ddx", "patient with", "case of",
            "year-old", "y/o", "presents with", "symptoms suggest"
        ]
        if any(keyword in full_query for keyword in diagnosis_keywords):
            return QueryType.DIFFERENTIAL_DIAGNOSIS
        
        # Default to general query
        return QueryType.GENERAL_QUERY


class ResponseValidator:
    """Response validation and sanitization."""
    
    @staticmethod
    def validate_response(response: str) -> Dict[str, Any]:
        """
        Validate AI response for safety and compliance.
        
        Args:
            response: AI response text
            
        Returns:
            Dict with validation results
        """
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Check for potentially harmful content
        harmful_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript protocol
            r'data:text/html',  # Data URLs
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                validation_result['is_valid'] = False
                validation_result['errors'].append('Potentially harmful content detected')
        
        # Check for excessive length
        if len(response) > 10000:  # 10KB limit
            validation_result['warnings'].append('Response exceeds recommended length')
        
        # Check for proper medical disclaimers
        if not any(disclaimer in response.lower() for disclaimer in [
            'qualified healthcare professional', 'clinical decision support', 'medical advice'
        ]):
            validation_result['warnings'].append('Missing medical disclaimer')
        
        return validation_result
    
    @staticmethod
    def sanitize_response(response: str) -> str:
        """
        Sanitize AI response.
        
        Args:
            response: AI response text
            
        Returns:
            Sanitized response
        """
        import html
        
        # HTML escape
        sanitized = html.escape(response)
        
        # Remove excessive whitespace
        sanitized = ' '.join(sanitized.split())
        
        return sanitized


class ConversationalService:
    """Enhanced conversational service with security features."""
    
    def __init__(self):
        """Initialize the conversational service."""
        try:
            # Initialize Google Cloud Vertex AI
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "regal-autonomy-454806-d1")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            
            logger.info(f"Initializing Vertex AI with project: {project_id}, location: {location}")
            vertexai.init(project=project_id, location=location)
            
            # Initialize the model
            self.model = GenerativeModel("gemini-2.5-flash")
            self.query_classifier = QueryClassifier()
            self.response_validator = ResponseValidator()
            
            logger.info("ConversationalService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ConversationalService: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"AI service initialization failed: {str(e)}"
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
            return 0.4  # Medium temperature for clinical reasoning
        else:
            return 0.3  # Lower temperature for general queries
    
    def _is_diagnosis_complete(self, response: str) -> bool:
        """Check if diagnosis is complete based on response content."""
        response_lower = response.lower().strip()
        incomplete_indicators = [
            "question:", "need more information", "additional information needed",
            "please provide", "can you tell me more"
        ]
        return not any(indicator in response_lower for indicator in incomplete_indicators)
    
    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
        retry=retry_if_not_exception_type(HTTPException)
    )
    async def generate_response(
        self, 
        query: str, 
        chat_history: str, 
        patient_data: str
    ) -> Tuple[str, bool]:
        """
        Generate AI response with enhanced security and validation.
        
        Args:
            query: User query
            chat_history: Previous conversation history
            patient_data: Patient data
            
        Returns:
            Tuple of (response_text, diagnosis_complete)
            
        Raises:
            HTTPException: If generation fails
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            query_validation = InputValidator.validate_patient_data(query)
            if not query_validation['is_valid']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid query: {query_validation['error']}"
                )
            
            patient_validation = InputValidator.validate_patient_data(patient_data)
            if not patient_validation['is_valid']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid patient data: {patient_validation['error']}"
                )
            
            # Use sanitized data
            sanitized_query = query_validation['sanitized_data']
            sanitized_patient_data = patient_validation['sanitized_data']
            sanitized_chat_history = InputValidator.validate_chat_history(chat_history or "")['sanitized_data']
            
            # Classify query type
            query_type = await self.query_classifier.classify_query(sanitized_query, sanitized_patient_data)
            
            # Retrieve context from vector store (increased k for more comprehensive context)
            context, sources = search_all_collections(sanitized_query, sanitized_patient_data, k=5)
            
            # Truncate context if too long to prevent token overflow
            max_context_length = 3000  # Increased to allow more comprehensive medical context
            if len(context) > max_context_length:
                context = context[:max_context_length] + "... [Context truncated due to length]"
                logger.warning(f"Context truncated from {len(context)} to {max_context_length} characters")
            
            # Format sources for display
            sources_text = ", ".join(sources) if sources else "No sources available"
            
            # Get prompt template and temperature
            prompt_template = self._get_prompt_template(query_type)
            temperature = self._get_temperature_setting(query_type)
            
            # Populate prompt
            prompt = prompt_template.format(
                patient_data=sanitized_patient_data,
                context=context,
                sources=sources_text,
                chat_history=sanitized_chat_history or "No previous conversation",
            )
            
            # Generate response
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=3000,  # Increased to match working configuration
                top_p=1.0,
            )
            
            response = await self.model.generate_content_async(
                prompt, 
                generation_config=generation_config
            )
            
            # Handle response safely
            try:
                response_text = response.text
            except Exception as e:
                # Handle cases where response is blocked or truncated
                if "MAX_TOKENS" in str(e) or "finish_reason" in str(e):
                    logger.warning(f"Response truncated due to token limit: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail="Response was truncated due to token limits. Please try with a shorter query or patient data."
                    )
                elif "safety filters" in str(e).lower():
                    logger.warning(f"Response blocked by safety filters: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail="Response was blocked by safety filters. Please rephrase your query."
                    )
                else:
                    logger.error(f"Unexpected error getting response text: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Unexpected error: {str(e)}"
                    )
            
            # Validate response
            validation_result = self.response_validator.validate_response(response_text)
            if not validation_result['is_valid']:
                SecureLogger.log_securely('warning', f'Response validation failed: {validation_result["errors"]}')
                raise HTTPException(
                    status_code=500,
                    detail="Response validation failed"
                )
            
            # Log warnings if any
            if validation_result['warnings']:
                SecureLogger.log_securely('warning', f'Response warnings: {validation_result["warnings"]}')
            
            # Sanitize response
            sanitized_response = self.response_validator.sanitize_response(response_text)
            
            # Determine if diagnosis is complete
            if query_type == QueryType.DRUG_INFORMATION or query_type == QueryType.GENERAL_QUERY:
                diagnosis_complete = True
            else:
                diagnosis_complete = self._is_diagnosis_complete(sanitized_response)
            
            # Log successful generation
            processing_time = time.time() - start_time
            SecureLogger.log_securely(
                'info',
                f'Response generated successfully',
                extra={
                    'query_type': query_type.value,
                    'processing_time': processing_time,
                    'response_length': len(sanitized_response),
                    'sources_count': len(sources),
                    'diagnosis_complete': diagnosis_complete
                }
            )
            
            return sanitized_response, diagnosis_complete
        
        except exceptions.ResourceExhausted:
            SecureLogger.log_securely('error', 'Google API resource exhausted')
            raise HTTPException(
                status_code=429, 
                detail="Rate limit exceeded or resource unavailable, please try again later."
            )
        
        except exceptions.GoogleAPIError as e:
            SecureLogger.log_securely('error', f'Google API error: {str(e)}')
            raise HTTPException(
                status_code=500, 
                detail=f"Model error: {str(e)}"
            )
        
        except Exception as e:
            SecureLogger.log_securely('error', f'Unexpected error in generate_response: {str(e)}')
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error: {str(e)}"
            )


# Global service instance
conversational_service = ConversationalService()


# Public API function
async def generate_response(query: str, chat_history: str, patient_data: str) -> Tuple[str, bool]:
    """
    Generate AI response with enhanced security.
    
    Args:
        query: User query
        chat_history: Previous conversation history
        patient_data: Patient data
        
    Returns:
        Tuple of (response_text, diagnosis_complete)
    """
    return await conversational_service.generate_response(query, chat_history, patient_data)