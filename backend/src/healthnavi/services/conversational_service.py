"""
Enhanced conversational service for HealthNavi AI CDSS.

This module provides secure AI conversation handling with proper validation,
audit logging, and data protection following medical software standards.
"""

import os
import time
import logging
import asyncio
import hashlib
from fastapi import HTTPException
from healthnavi.services.genai_client import get_genai_client
from healthnavi.services.vectorstore_manager import search_all_collections
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
from dotenv import load_dotenv
from typing import Dict, Tuple
from google.api_core import exceptions
from enum import Enum
# import concurrent.futures  # Not used in this implementation
from datetime import datetime, timedelta

from healthnavi.core.constants import (
    MODEL_NAME, PROMPT_TOKEN_LIMIT, CACHE_TTL_MINUTES, MAX_CACHE_SIZE,
    DEFAULT_CONTEXT_MAX_CHARS, BALANCED_CONTEXT_MAX_CHARS,
    MAX_RETRY_ATTEMPTS, RETRY_MULTIPLIER, RETRY_MIN_WAIT, RETRY_MAX_WAIT
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
load_dotenv()

# GenAI client will be initialized at startup

# Simple in-memory cache for responses
RESPONSE_CACHE: Dict[str, Tuple[str, datetime]] = {}

class QueryType(Enum):
    DRUG_INFORMATION = "drug_information"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    GENERAL_QUERY = "general_query"
    
GENERAL_PROMPT = """
YOU ARE **HealthNavy**, A CLINICAL DECISION SUPPORT SYSTEM (CDSS) BUILT USING RETRIEVAL-AUGMENTED GENERATION (RAG) TECHNOLOGY. YOU POSSESS ACCESS TO A CURATED KNOWLEDGE BASE CONSISTING OF CLINICAL TEXTS, GUIDELINES, RESEARCH ARTICLES, AND DRUG MANUALS STORED IN A VECTOR DATABASE. YOUR PRIMARY FUNCTION IS TO PROVIDE ACCURATE, EVIDENCE-BASED MEDICAL ANSWERS DRAWN FROM RETRIEVED CONTEXT. WHEN INFORMATION IS MISSING OR INCOMPLETE, YOU MUST FALL BACK TO YOUR INTERNAL GENERAL MEDICAL KNOWLEDGE AND PROVIDE VALID REFERENCES.

---

### OBJECTIVE

TO DELIVER AUTHORITATIVE, EVIDENCE-BASED, AND PROFESSIONALLY FORMATTED CLINICAL RESPONSES COVERING:
- DIFFERENTIAL DIAGNOSES  
- DRUG INTERACTIONS AND CONTRAINDICATIONS  
- GENERAL MEDICAL AND PATHOPHYSIOLOGICAL QUERIES  
- DIAGNOSTIC ALGORITHMS AND MANAGEMENT PLANS  
- MULTIPLE-CHOICE CLINICAL QUESTIONS (MCQs) WITH EXPLANATIONS  

---

### EXECUTION RULES

1.### CRITICAL FORMATTING RULES - MUST FOLLOW:**
- ALWAYS put a BLANK LINE (press ENTER twice) after each **HEADING**
- ALWAYS put a BLANK LINE before starting a new **HEADING**
- Each list item (1. 2. 3. or -) must be on its OWN separate line
- NEVER write content on the same line as the heading
- Pattern: **HEADING**[ENTER][ENTER]Content starts here[ENTER][ENTER]**NEXT HEADING**

2. **PRIMARY KNOWLEDGE SOURCE**
   - ALWAYS PRIORITIZE INFORMATION RETRIEVED FROM `{context}` (REFERENCE TEXTS).
   - WHEN REFERENCE TEXT DOES NOT ADDRESS THE QUESTION SUFFICIENTLY, FALL BACK TO MODEL KNOWLEDGE AND GIVE VALID REFERENCES`.

3. **CITATIONS**
   - Cite as `[Source: document_name or filename.pdf]`.

4. **AGE-SPECIFIC CONTEXT**
   - IF PATIENT AGE < 18 → use pediatric references first.
   - IF PATIENT AGE ≥ 18 → use adult guidelines and avoid pediatric sources.

5. **MCQ / OBJECTIVE QUESTION HANDLING**
   - IF THE QUERY CONTAINS MULTIPLE CHOICE OPTIONS (A, B, C, D, etc.):
     - SELECT THE CORRECT ANSWER BASED ON EVIDENCE AND CONTEXT.
     - EXPLAIN WHY IT IS CORRECT USING CLINICAL REASONING.
     - BRIEFLY EXPLAIN WHY OTHER OPTIONS ARE INCORRECT.

   **REQUIRED FORMAT:**
Correct Answer: (X) [Option text]
Explanation: [Reasoning with citations]
Why other options are wrong:

(Y) [Brief reason]

(Z) [Brief reason]

6. **CLINICAL / OPEN QUESTIONS HANDLING**
- PROVIDE A STRUCTURED RESPONSE USING THE FOLLOWING FORMAT:

**Summary**: 
[Concise context or definition with citation]
**Differential Diagnosis** (if applicable):

[Condition 1] — [Rationale + citation]

[Condition 2] — [Rationale + citation]

Investigations / Workup:

[Test 1] — [Purpose]

[Test 2] — [Purpose]

Management:

[First-line approach + citation]

[Alternative options]

References: [List all sources used]

6. **FALLBACK BEHAVIOR**
- IF RETRIEVED KNOWLEDGE BASE `{context}` IS EMPTY OR IRRELEVANT:
  - USE INTERNAL MODEL KNOWLEDGE.
  - ALWAYS INCLUDE RELEVANT REFERENCES (e.g., UpToDate, PubMed, or standard clinical guidelines).

7. **STYLE AND LENGTH**
- BE PROFESSIONAL, OBJECTIVE, AND CONCISE (<500 WORDS).
- USE BULLET POINTS, HEADINGS, AND BOLD TEXT FOR CLARITY.

### CHAIN OF THOUGHTS (MANDATORY INTERNAL REASONING)

FOLLOW THIS STEPWISE APPROACH INTERNALLY BEFORE PRODUCING ANY OUTPUT:

<chain_of_thoughs_rules>
1. **UNDERSTAND:** IDENTIFY THE CORE QUESTION OR TASK (clinical reasoning, MCQ, diagnosis, etc.).
2. **BASICS:** RECALL FUNDAMENTAL MEDICAL PRINCIPLES RELATED TO THE QUERY.
3. **BREAK DOWN:** DECOMPOSE INTO RELEVANT SUBCOMPONENTS (e.g., differential diagnosis, investigations, treatment).
4. **ANALYZE:** CROSS-REFERENCE RETRIEVED CONTEXT FROM `{context}` WITH KNOWN MEDICAL FACTS.
5. **BUILD:** SYNTHESIZE FINDINGS INTO A STRUCTURED, LOGICAL ANSWER.
6. **EDGE CASES:** CONSIDER EXCEPTIONS, AGE VARIATIONS, OR CONTRAINDICATIONS.
7. **FINAL ANSWER:** PRESENT THE INFORMATION PROFESSIONALLY WITH SOURCES AND CLEAR FORMATTING.
</chain_of_thoughs_rules>


### WHAT NOT TO DO

- NEVER PROVIDE UNSUPPORTED OR UNCITED MEDICAL CLAIMS.  
- NEVER INVENT REFERENCES OR SOURCES.  
- NEVER GUESS — IF DATA IS INSUFFICIENT, FALL BACK TO MODEL KNOWLEDGE.  
- NEVER MIX PEDIATRIC AND ADULT GUIDELINES INAPPROPRIATELY.  
- NEVER GIVE AMBIGUOUS OR UNSTRUCTURED OUTPUTS.  
- NEVER OMIT “REFERENCES” SECTION FROM THE RESPONSE.  

**AVAILABLE SOURCES:** {sources}  
**REFERENCE TEXT:** {context}
"""

def optimize_context_for_llm(context: str, max_chars: int = DEFAULT_CONTEXT_MAX_CHARS) -> str:
    """Optimize context to reduce input tokens while preserving key information.
    Set to 1200 chars (~300 tokens) for balance between speed and quality."""
    if not context or len(context) <= max_chars:
        return context
    # Take from the beginning (most relevant results)
    return context[:max_chars] + "\n... [Context truncated for speed]"

async def classify_query(query: str, patient_data: str) -> QueryType:
    """Classify the query using rules to determine the user's intent."""
    # TEMPORARILY: Always use GENERAL_QUERY format
    return QueryType.GENERAL_QUERY

def is_diagnosis_complete(response: str) -> bool:
    return "question:" not in response.lower().strip()

def _generate_cache_key(query: str, patient_data: str) -> str:
    """Generate a cache key from query and patient data."""
    combined = f"{query}|{patient_data}".lower().strip()
    return hashlib.md5(combined.encode()).hexdigest()

def _get_cached_response(cache_key: str) -> str:
    """Get cached response if available and not expired."""
    if cache_key in RESPONSE_CACHE:
        response, timestamp = RESPONSE_CACHE[cache_key]
        if datetime.now() - timestamp < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info(f"Cache HIT - Returning cached response (age: {(datetime.now() - timestamp).seconds}s)")
            return response
        else:
            # Expired, remove from cache
            del RESPONSE_CACHE[cache_key]
            logger.info("Cache EXPIRED - Will generate new response")
    return None

def _cache_response(cache_key: str, response: str):
    """Cache a response with timestamp."""
    RESPONSE_CACHE[cache_key] = (response, datetime.now())
    logger.info(f"Response cached (cache size: {len(RESPONSE_CACHE)} entries)")
    
    # Cleanup old entries if cache gets too large
    if len(RESPONSE_CACHE) > MAX_CACHE_SIZE:
        # Remove oldest entries
        sorted_keys = sorted(RESPONSE_CACHE.keys(), key=lambda k: RESPONSE_CACHE[k][1])
        for key in sorted_keys[:20]:  # Remove 20 oldest
            del RESPONSE_CACHE[key]
        logger.info(f"🧹 Cache cleanup - Removed 20 oldest entries")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
    retry=retry_if_not_exception_type(HTTPException)
)
async def generate_response(query: str, chat_history: str, patient_data: str) -> Tuple[str, bool, str]:
    
    total_start_time = time.time()
    full_response_text = ""  # Initialize at outer scope
    
    try:
        # Check cache first (skip for queries with chat history)
        cache_key = None
        if not chat_history or chat_history == "No previous conversation":
            cache_key = _generate_cache_key(query, patient_data)
            cached_response = _get_cached_response(cache_key)
            if cached_response:
                logger.info(f"⚡ Cached response returned in {time.time() - total_start_time:.3f}s")
                diagnosis_complete = is_diagnosis_complete(cached_response)
                return cached_response, diagnosis_complete, QueryType.GENERAL_QUERY.value
        
        # ... (Steps 1-3: Classify, Retrieve, Optimize, Prepare)
        query_type = await classify_query(query, patient_data)
        logger.info(f"Query type: {query_type.value}")

        # Reduce k from 5 to 3 for faster search and less context
        context, actual_sources = search_all_collections(query, patient_data, k=5)
        optimized_context = optimize_context_for_llm(context, max_chars=BALANCED_CONTEXT_MAX_CHARS)  # Balanced for quality
        logger.info(f"Context optimized: {len(context)} -> {len(optimized_context)} chars")

        sources_text = ", ".join(actual_sources) if actual_sources else "No sources available"
        
        # TEMPORARILY: Always use GENERAL_PROMPT
        prompt_template = GENERAL_PROMPT

        full_prompt = prompt_template.format(sources=sources_text, context=optimized_context)
        full_prompt += f"\n\nQUERY: {query}\n\nPATIENT INFO: {patient_data}\n\nPREVIOUS CONVERSATION: {chat_history or 'No previous conversation'}"
        
        logger.info(f"--- PROMPT SENT TO API (first 500 chars) ---\n{full_prompt[:500]}\n...")

        # Step 4: Generate Content 
        llm_start = time.time()
        logger.info(f"Generating response...")

        # Get the GenAI client
        client = get_genai_client()

        try:
            # Count tokens using the new API
            token_count_response = client.models.count_tokens(
                model=MODEL_NAME,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}]
            )
            prompt_token_count = token_count_response.total_tokens
            logger.info(f"Calculated input prompt token count: {prompt_token_count}")
            if prompt_token_count > PROMPT_TOKEN_LIMIT:
                error_msg = f"Error: Input prompt exceeds token limit ({prompt_token_count}/{PROMPT_TOKEN_LIMIT})."
                logger.error(error_msg)
                return error_msg, False, QueryType.GENERAL_QUERY.value
        except Exception as e:
            logger.error(f"Could not count tokens for the prompt: {e}")
            return "Error: Could not validate the prompt's length.", False, QueryType.GENERAL_QUERY.value

        logger.info("Generating response...")
        
        try:
            # Generate content using the new API
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
                config={
                    "temperature": 0.2,
                    "max_output_tokens": 3000,
                    "top_p": 0.9,
                    "top_k": 40,
                    "candidate_count": 1
                }
            )
        except Exception as e:
            logger.error(f"Failed to generate content: {e}", exc_info=True)
            return f"Failed to start content generation: {str(e)}", False, QueryType.GENERAL_QUERY.value
        
        try:
            if response and hasattr(response, 'candidates') and response.candidates:
                # Extract text from the first candidate
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    full_response_text = candidate.content.parts[0].text.strip()
                    logger.info(f"⚡ Response generated in {time.time() - llm_start:.3f}s")
                else:
                    logger.error("Response content was empty or malformed")
                    return "Content was blocked. Please rephrase your medical query with more clinical terminology.", False, QueryType.GENERAL_QUERY.value
            else:
                logger.error("Response was empty or blocked by safety filters")
                return "Content was blocked. Please rephrase your medical query with more clinical terminology.", False, QueryType.GENERAL_QUERY.value

        except Exception as e:
            logger.error(f"Error processing response: {e}", exc_info=True)
            return f"An error occurred: {str(e)}", False, QueryType.GENERAL_QUERY.value

        # Cache the complete response if applicable
        if cache_key and full_response_text:
            _cache_response(cache_key, full_response_text)
            
        logger.info(f"Total generation completed in {time.time() - llm_start:.3f}s")
        logger.info(f"Full pipeline completed in {time.time() - total_start_time:.3f}s")
        
        # Determine if diagnosis is complete
        diagnosis_complete = is_diagnosis_complete(full_response_text)
        
        # Return the response with metadata in the expected format
        return full_response_text, diagnosis_complete, QueryType.GENERAL_QUERY.value

    except Exception as e:
        # Catch any other unexpected errors at the top level
        logger.error(f"FATAL error in generate_response: {e}", exc_info=True)
        error_message = f"An unexpected error occurred: {str(e)}"
        return error_message, False, QueryType.GENERAL_QUERY.value
