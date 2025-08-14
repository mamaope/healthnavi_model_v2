import os
import json
import asyncio
import time
from fastapi import HTTPException
from vertexai.generative_models import GenerativeModel, GenerationConfig
from app.services.vectordb_service import retrieve_context
import app.auth
from dotenv import load_dotenv
from typing import Dict
from google.api_core import exceptions
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv()

PROMPT_TEMPLATE = """
You are an expert medical AI, designed to assist a qualified doctor. Your task is to analyze patient information and provide a structured clinical assessment based ONLY on the provided reference materials.

IMPORTANT: You must follow all rules listed below.

---
RULES:
1.  **Source of Truth**: Base your entire analysis strictly on the `REFERENCE TEXT TO USE`. Do NOT reference sources that are not explicitly provided in the knowledge base.
2.  **Selective Citations**: Only cite sources when:
    - Making specific clinical recommendations or diagnostic criteria
    - Stating clinical guidelines or protocols
    - Referencing specific diagnostic tests or treatment approaches
    - Quoting or paraphrasing specific clinical information
   Do NOT cite sources for general medical knowledge, basic pathophysiology, or common clinical observations.
3.  **Accurate Citations**: When citing, use ONLY the exact source names from the `AVAILABLE KNOWLEDGE BASE SOURCES` list. Include page numbers, section names, or specific document identifiers when available in the format: `[Source: document_name, page/section]`.
4.  **Medical Acronyms**: Interpret and correctly use common medical acronyms.
5.  **Vital Signs First**: Always begin your analysis by checking the patient's vital signs. If any are in a dangerous range, issue an "ALERT" immediately and suggest urgent interventions. Do not proceed with a differential diagnosis if there's an immediate life threats.
6.  **Output Format**: Choose ONE of the following formats for your complete response based on the situation:

    * **If vital signs are dangerous:**
        - Start with "ALERT: [Description of the critical issue]."
        - Provide a bulleted list of immediate actions.

    * **If you need more information to make a diagnosis:**
        - **Question:** [Ask one clear, focused question for the most critical missing piece of information.]
        - **Rationale:** [Explain why this information is essential for diagnosis, citing reference material if available.]
        - **Sources:** {sources}

    * **If you have enough information for an assessment:**
        - Provide either a "DIFFERENTIAL DIAGNOSIS" or an "ASSESSMENT AND PLAN".
        - **DIFFERENTIAL DIAGNOSIS**
            - **Case Discussion:** {{one to two paragraph discussion of the case and the differential diagnosis}}
            - **Most Likely Diagnoses:**
                - {{Most_Likely_Diagnosis1}}: {{discussion of supporting/opposing evidence with selective citations only where specific guidelines exist}}
                - {{Most_Likely_Diagnosis2}}: {{discussion of supporting/ignore evidence with selective citations only where specific guidelines exist}}
            - **Expanded Differential:**
                - {{Expanded_Diagnosis1}}: {{discussion with selective citations only where specific guidelines exist}}
        - **ASSESSMENT AND PLAN**
            - **Clinical Impression:** {{Your overall clinical impression}}
            - **# {{Problem 1}}**
                - {{Assessment of the problem}}
                - **Dx:** {{Diagnostic next steps}}
                - **Tx:** {{Treatment next steps}}
        - **Sources:** {sources}
        - *This application is for clinical decision support and should only be used by qualified healthcare professionals.*
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
Evaluate the patient's information according to the rules and provide your response in the specified format. Remember: cite only when referencing specific clinical guidelines, protocols, or criteria from the provided sources. Do not cite general medical knowledge or make up source names.
"""

def is_diagnosis_complete(response: str) -> bool:
    response_lower = response.lower().strip()
    return "question:" not in response_lower    

def validate_citations(response: str, actual_sources: list[str]) -> str:
    """Validate that all citations in the response reference actual sources from the knowledge base."""
    if not actual_sources:
        return response
    
    # Create a set of valid source names (case-insensitive)
    valid_sources = {source.lower() for source in actual_sources}
    
    # Find all citation patterns in the response
    import re
    citation_pattern = r'\[Source:\s*([^\]]+)\]'
    
    def validate_citation(match):
        cited_source = match.group(1).strip()
        # Check if the cited source exists in our knowledge base
        if not any(cited_source.lower() in valid_source for valid_source in valid_sources):
            # If source not found, remove the citation but keep the text
            return ""
        return match.group(0)
    
    # Replace invalid citations
    validated_response = re.sub(citation_pattern, validate_citation, response)
    
    return validated_response

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_response(query: str, chat_history: str, patient_data: str, retriever):
    """Generate a diagnostic response using the LLM and retrieved context."""
    try:
        start_time = time.time()

        # Retrieve context and actual sources
        context, actual_sources = retrieve_context(query, patient_data, retriever)
        
        # Format sources for display
        sources_text = ", ".join(actual_sources) if actual_sources else "No sources available"
        
        # Populate prompt
        prompt = PROMPT_TEMPLATE.format(
            patient_data=patient_data,
            context=context,
            sources=sources_text,
            chat_history=chat_history or "No previous conversation",
        )

        # Generate model response with Vertex AI
        model = GenerativeModel("gemini-2.5-pro")
        generation_config = GenerationConfig(
            temperature=0.4,  # Lowered for more deterministic and faster clinical responses
            max_output_tokens=3000,
            top_p=1.0,
        )
        
        response = await model.generate_content_async(prompt, generation_config=generation_config)
        
        response_text = response.text
        
        # Validate citations to ensure they only reference actual sources
        validated_response = validate_citations(response_text, actual_sources)
        
        diagnosis_complete = is_diagnosis_complete(validated_response)
        
        return validated_response, diagnosis_complete
    
    except exceptions.ResourceExhausted:
        raise HTTPException(status_code=429, detail="Rate limit exceeded or resource unavailable, please try again later.")
    except exceptions.GoogleAPIError as e:
        raise HTTPException(status_code=500, detail=f"Model error: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
