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
YOU ARE **HealthNavy**, a clinical decision support system (CDSS) providing evidence-based medical assistance.

---

### OBJECTIVE
To deliver authoritative, evidence-based, and professionally formatted clinical responses covering:
- Differential Diagnoses
- Drug Interactions and Contraindications
- General Medical and Pathophysiological Queries
- Diagnostic Algorithms and Management Plans
- Multiple-Choice Clinical Questions (MCQs) with Explanations

---

### CORE DIRECTIVES

1.  **AUTHORITY & CITATIONS:**
    - **CRITICAL: You must speak as a direct expert.
    - **AVOID ALL PHRASES LIKE:** "The provided text indicates...", "The provided text states...", "According to the context...", "The reference material shows...",etc.
    - **INSTEAD:** State facts directly and append the citation. for example, "Hypertension is defined as...".
    - The `{context}` provided is your authoritative knowledge base. Integrate it seamlessly into your answer.
    - If the knowledge base does not contain the answer, use your general medical knowledge, citing reputable public sources (e.g., PubMed).
    - **ALWAYS** cite your sources using `[Source: document_name]`.
    - **EVERY RESPONSE MUST END WITH A "References" SECTION** listing all sources used.

2.  **FORMATTING & STYLE:**
    - Responses must be professional, objective, and clear.
    - Use headings, bold text, and bullet points for clarity.
    - **CRITICAL:** Always place a blank line (two newlines) before and after every heading. Do not write content on the same line as a heading.

3.  **CONCISENESS & LENGTH:**
    - **BE CONCISE.** Your entire response, including references, must be under 500 words.
    - Focus on the most critical, high-yield information.
    - Avoid verbose explanations or unnecessary background information.

4.  **AGE-SPECIFIC CONTEXT:**
    - For patients < 18, prioritize pediatric guidelines.
    - For patients ≥ 18, use adult guidelines.

---

### RESPONSE STRUCTURES

1.  **For Multiple-Choice Questions (MCQs):**
    Use this exact format:
    **Correct Answer:** (X) [Option text]
    **Explanation:** [Detailed reasoning with citations on why the answer is correct. (MAX 4 SENTENCES TOTAL)]
    **Why other options are wrong:**
    - (Y) [Brief reason. (MAX 1 SENTENCE)]
    - (Z) [Brief reason. (MAX 1 SENTENCE)]
    **References**
    - [List all sources used.]

2.  **For Clinical / Open Questions:**
    Use this structured format:
    **Summary**
    [Concise overview or definition with citation. (MAX 2 SENTENCES)]
    **Differential Diagnosis** (if applicable):
    - [Condition 1] — [Rationale + citation. (MAX 1 SENTENCE RATIONALE)]
    - [Condition 2] — [Rationale + citation. (MAX 1 SENTENCE RATIONALE)]
    **Investigations / Workup**:
    - [Test 1] — [Purpose. (MAX 1 SENTENCE PURPOSE)]
    - [Test 2] — [Purpose. (MAX 1 SENTENCE PURPOSE)]
    **Management**
    - [First-line approach + citation. (MAX 2 SENTENCES TOTAL)]
    - [Alternative options. (MAX 1 SENTENCE)]
    **References**
    - [List all sources used.]

---

### CRITICAL PROHIBITIONS
- NEVER invent information or sources.
- NEVER provide medical advice without a citation.
- NEVER give an ambiguous or unstructured answer.

**AVAILABLE SOURCES:** {sources}
**EVIDENCE BASE:** {context}
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
        
        # Classify, Retrieve, Optimize, Prepare
        query_type = await classify_query(query, patient_data)
        logger.info(f"Query type: {query_type.value}")

        context, actual_sources = search_all_collections(query, patient_data, k=6)
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
            # Do not fail hard if token counting endpoint is unavailable; proceed to generation
            logger.warning(f"Token count unavailable, proceeding without validation: {e}")

        logger.info("Generating response...")
        
        try:
            # Generate content using the new API
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
                config={
                    "temperature": 0.2,
                    "max_output_tokens": 4000,
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
                candidate = response.candidates[0]
                
                # check if content exists AT ALL. 
                if not (hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts):
                    logger.error("Response was empty or blocked. Candidate exists but has no content parts.")
                    return "Content was blocked. Please rephrase your medical query with more clinical terminology.", False, QueryType.GENERAL_QUERY.value

                # Get the text part
                full_response_text = candidate.content.parts[0].text.strip()
                
                # Get the finish reason
                finish_reason = getattr(candidate, 'finish_reason', 'UNKNOWN')
                logger.info(f"Response finish reason: {finish_reason}")
                
                if finish_reason == 'MAX_TOKENS':
                    logger.warning(f"Response generation hit MAX_TOKENS limit. Response is TRUNCATED.")
                    # Append a clear warning to the user
                    full_response_text += "\n\n**[WARNING: The response was truncated because it exceeded the maximum output length. Please ask a more specific follow-up question if needed.]**"
                elif finish_reason == 'SAFETY':
                    logger.warning("Response generation was cut short due to SAFETY filters.")
                    full_response_text += "\n\n**[WARNING: The response was partially blocked by safety filters.]**"
                elif finish_reason == 'RECITATION':
                    logger.warning("Response generation was cut short due to RECITATION filters.")
                elif finish_reason == 'STOP':
                    logger.info(f"⚡ Response generated successfully in {time.time() - llm_start:.3f}s (Finish: STOP)")
                else:
                    logger.warning(f"Response finished with unhandled reason: {finish_reason}")

            else:
                logger.error("Response was empty or blocked by safety filters (no candidates returned)")
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
