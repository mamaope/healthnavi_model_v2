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
from typing import Dict, Tuple, List, Optional
from enum import Enum
from fastapi import HTTPException
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.api_core import exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type

from app.core.config import get_config
from app.core.security import SecureLogger, InputValidator, EncryptionService
from app.services.vectorstore_manager import search_all_collections

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
**CLINICAL OVERVIEW**  
[1–2 paragraph summary of the case, highlighting key clinical features and initial impression]

**DIFFERENTIAL DIAGNOSES**  
1. **[Primary Diagnosis]** (XX%): [Brief justification with supporting/opposing evidence; cite only if guideline/protocol reference is used]  
2. **[Secondary Diagnosis]** (XX%): [Justification]  
3. **[Tertiary Diagnosis]** (XX%): [Justification]  
[Add additional diagnoses if clinically relevant]

**IMMEDIATE WORKUP & INVESTIGATIONS**  
- [Essential tests and investigations, prioritized by urgency]  
- [Include time-sensitive protocols if relevant]

**MANAGEMENT & RECOMMENDATIONS**  
- [Immediate/urgent management steps]  
- [Evidence-based treatment recommendations]  
- [Monitoring requirements and follow-up]

**RED FLAGS / DANGER SIGNS**  
- [List warning signs needing urgent escalation]  

**ADDITIONAL INFORMATION NEEDED** (if applicable)  
[One critical, focused question to refine diagnosis/management]

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
5.  **Output Format**: Structure your response using the following format:

**DRUG OVERVIEW**
[Provide a brief overview of the drug based on the knowledge base, including what it is, active ingredients, and primary indications]

**SIDE EFFECTS**
[List side effects by frequency categories as found in the knowledge base:
- Very Common (>1/10)
- Common (1/100 to 1/10) 
- Uncommon (1/1,000 to 1/100)
- Rare (1/10,000 to 1/1,000)
- Very Rare (<1/10,000)
- Unknown frequency
Only include categories that have documented side effects in the knowledge base]

**DRUG INTERACTIONS**
[List known drug interactions from the knowledge base. If none are documented, state "No drug interactions documented in knowledge base."]

**CONTRAINDICATIONS**
[List contraindications from the knowledge base. If none are documented, state "No contraindications documented in knowledge base."]

**MECHANISM OF ACTION** (if available)
[Include molecular targets, mechanisms of action, and pharmacological information if available in the knowledge base]

**CHEMICAL INFORMATION** (if available)
[Include ChEMBL ID, molecule type, and other chemical details if available]

**Sources:** {sources}

*This application is for clinical decision support and should only be used by qualified healthcare professionals.*

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
"""

    GENERAL_PROMPT = """
You are a medical AI assistant. Answer the user's question based ONLY on the provided reference materials from the knowledge base.

IMPORTANT: You must follow these formatting rules:

1. **Opening Context**: Start with 1-2 sentences providing brief context about the medical topic being asked about.

2. **Main Content**: Organize your response using clear headings and bullet points when listing symptoms, treatments, or information:
   - Use headings like "Common symptoms:", "Signs that suggest [condition]:", "Treatment options:", etc.
   - Use bullet points for lists of symptoms, signs, or recommendations
   - Be direct and factual - no conversational greetings or filler words

3. **References**: Include specific citations when stating medical facts, guidelines, or recommendations using the format [Source: document_name, page/section]

4. **Warnings**: If discussing serious conditions, end with appropriate medical warnings.

5. **Knowledge Base Only**: Base your entire response on the provided reference materials.

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
        self.model = GenerativeModel("gemini-2.5-flash")
        self.query_classifier = QueryClassifier()
        self.response_validator = ResponseValidator()
    
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
            
            # Retrieve context from vector store
            context, sources = search_all_collections(sanitized_query, sanitized_patient_data, k=5)
            
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
                max_output_tokens=3000,
                top_p=1.0,
            )
            
            response = await self.model.generate_content_async(
                prompt, 
                generation_config=generation_config
            )
            
            response_text = response.text
            
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