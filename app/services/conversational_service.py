import os
import json
import asyncio
import time
import logging
import re
from fastapi import HTTPException
from vertexai.generative_models import GenerativeModel, GenerationConfig
from app.services.vectorstore_manager import search_all_collections
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
import app.auth
from dotenv import load_dotenv
from typing import Dict, Tuple
from google.api_core import exceptions
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class QueryType(Enum):
    DRUG_INFORMATION = "drug_information"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    GENERAL_QUERY = "general_query"

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

QUERY_CLASSIFICATION_PROMPT = """
Classify this medical query. Respond with ONLY valid JSON.

DIFFERENTIAL_DIAGNOSIS:
- Contains age + gender + symptoms (e.g., "65-year-old woman with chest pain")
- Asks for "differential diagnosis" or "ddx" 
- Describes a specific patient case
- Examples: "Patient presents with fever", "Draft differential diagnosis", "30-year-old man with abdominal pain"

DRUG_INFORMATION:
- Questions about specific medications/drugs
- Examples: "side effects of aspirin", "contraindications for ibuprofen", "dosing of paracetamol"

GENERAL_QUERY:
- General medical knowledge questions
- NOT about specific patients or specific drugs
- Examples: "What are signs of malaria?", "How is diabetes treated?"

Query: "{full_query}"

Rules:
1. If mentions specific drug/medication → "drug_information"
2. If describes patient case or asks for differential → "differential_diagnosis"  
3. Otherwise → "general_query"

{{"query_type": "general_query"}}
"""

async def classify_query(query: str, patient_data: str) -> QueryType:
    """Classify the query using rules to determine the user's intent."""
    full_query = f"{query} {patient_data}".lower().strip()

    # Rule for drug information
    drug_keywords = [
        "side effects of", "contraindications for", "dosing of", 
        "interactions of"
    ]
    if any(keyword in full_query for keyword in drug_keywords):
        # More specific check for drug names can be added if a list is available
        return QueryType.DRUG_INFORMATION

    # Rule for differential diagnosis
    diagnosis_keywords = [
        "differential diagnosis", "ddx", "patient with", "case of",
        "year-old", "y/o", "presents with"
    ]
    if any(keyword in full_query for keyword in diagnosis_keywords):
        return QueryType.DIFFERENTIAL_DIAGNOSIS

    # Default to general query
    return QueryType.GENERAL_QUERY

def is_diagnosis_complete(response: str) -> bool:
    response_lower = response.lower().strip()
    return "question:" not in response_lower

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
    retry=retry_if_not_exception_type(HTTPException)
)
async def generate_response(query: str, chat_history: str, patient_data: str):
    """Generate a response using the LLM and retrieved context, with different prompts based on query type."""
    try:
        start_time = time.time()

        # Detect query type to determine appropriate prompt
        query_type = await classify_query(query, patient_data)
        
        # Retrieve context and actual sources from both collections
        context, actual_sources = search_all_collections(query, patient_data, k=5)
        
        # Format sources for display
        sources_text = ", ".join(actual_sources) if actual_sources else "No sources available"
        
        # Select appropriate prompt template based on query type
        if query_type == QueryType.DRUG_INFORMATION:
            prompt_template = DRUG_INFORMATION_PROMPT
            temperature = 0.2
        elif query_type == QueryType.DIFFERENTIAL_DIAGNOSIS:
            prompt_template = DIFFERENTIAL_DIAGNOSIS_PROMPT
            temperature = 0.4
        else:
            prompt_template = GENERAL_PROMPT
            temperature = 0.3 
        
        # Populate prompt
        prompt = prompt_template.format(
            patient_data=patient_data,
            context=context,
            sources=sources_text,
            chat_history=chat_history or "No previous conversation",
        )

        # Generate model response with Vertex AI
        model = GenerativeModel("gemini-2.5-flash")
        generation_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=3000,
            top_p=1.0,
        )
        
        response = await model.generate_content_async(prompt, generation_config=generation_config)
        
        response_text = response.text
        
        if query_type == QueryType.DRUG_INFORMATION or query_type == QueryType.GENERAL_QUERY:
            diagnosis_complete = True
        else:
            diagnosis_complete = is_diagnosis_complete(response_text)
        
        return response_text, diagnosis_complete
    
    except exceptions.ResourceExhausted:
        logger.error("Google API resource exhausted")
        raise HTTPException(status_code=429, detail="Rate limit exceeded or resource unavailable, please try again later.")
    except exceptions.GoogleAPIError as e:
        logger.error(f"Google API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Model error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in generate_response: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
