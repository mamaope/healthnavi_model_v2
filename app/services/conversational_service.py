

# class QueryType(Enum):
#     DRUG_INFORMATION = "drug_information"
#     DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
#     GENERAL_QUERY = "general_query"

# DIFFERENTIAL_DIAGNOSIS_PROMPT = """
# Expert medical AI for qualified doctors. Generate structured clinical assessment using ONLY provided reference materials.

# RULES:
# 1. **Source-Only**: Use only `REFERENCE TEXT`. No external knowledge.
# 2. **Citations**: Cite for guidelines/protocols/treatments only. Format: `[Source: document_name]`
# 3. **Critical First**: Start with ** CRITICAL ALERT** if immediate danger exists.
# 4. **Probabilities**: Assign realistic percentages (sum ~100%).
# 5. **Concise**: Direct, clinical documentation style.

# FORMAT:
# **CLINICAL OVERVIEW**
# [1-2 sentences: key features, initial impression]

# **DIFFERENTIAL DIAGNOSES**
# 1. **[Diagnosis]** (XX%): [Brief justification]
# 2. **[Diagnosis]** (XX%): [Brief justification]
# 3. **[Diagnosis]** (XX%): [Brief justification]

# **IMMEDIATE WORKUP**
# - [Essential tests, prioritized]

# **MANAGEMENT**
# - [Immediate steps]
# - [Treatment recommendations]

# **RED FLAGS**
# - [Warning signs requiring escalation]

# **Sources:** {sources}

# REFERENCE TEXT: {context}
# PATIENT INFO: {patient_data}
# PREVIOUS: {chat_history}
# """

# DRUG_INFORMATION_PROMPT = """
# Expert pharmacology AI for healthcare professionals. Provide drug information using ONLY the reference materials.

# RULES:
# 1. **Source-Only**: Use only `REFERENCE TEXT`. State "Not in knowledge base" if missing.
# 2. **Citations**: Include full source names and URLs when available.
# 3. **Exact Names**: Use drug names exactly as in knowledge base.

# FORMAT:
# **DRUG OVERVIEW**
# [Brief: what it is, active ingredients, primary uses]

# **SIDE EFFECTS** (by frequency if available)
# - Very Common (>1/10): [list]
# - Common (1/100-1/10): [list]
# - Uncommon/Rare: [list]

# **INTERACTIONS**
# [Known interactions or "None documented"]

# **CONTRAINDICATIONS**
# [List or "None documented"]

# **MECHANISM** (if available)
# [Targets, action, pharmacology]

# **Sources:** {sources}

# REFERENCE TEXT: {context}
# DRUG QUERY: {patient_data}
# PREVIOUS: {chat_history}
# """

# GENERAL_PROMPT = """
# Medical AI assistant. Answer using ONLY the provided reference materials.

# RULES:
# 1. **Source-Only**: Base response on `REFERENCE TEXT` only.
# 2. **Citations**: Use format `[Source: document_name]` for medical facts.
# 3. **Structure**: Use clear headings and bullet points.

# FORMAT:
# [1-2 sentences context about the topic]

# **[Relevant Heading]:**
# - [Key points as bullets]

# **[Another Heading if needed]:**
# - [Additional information]

# **Sources:** {sources}

# REFERENCE TEXT: {context}
# QUERY: {patient_data}
# PREVIOUS: {chat_history}
# """

# async def classify_query(query: str, patient_data: str) -> QueryType:
#     """Classify the query using rules to determine the user's intent."""
#     full_query = f"{query} {patient_data}".lower().strip()

#     # Rule for drug information
#     drug_keywords = [
#         "side effects of", "contraindications for", "dosing of", 
#         "interactions of"
#     ]
#     if any(keyword in full_query for keyword in drug_keywords):
#         # More specific check for drug names can be added if a list is available
#         return QueryType.DRUG_INFORMATION

#     # Rule for differential diagnosis
#     diagnosis_keywords = [
#         "differential diagnosis", "ddx", "patient with", "case of",
#         "year-old", "y/o", "presents with"
#     ]
#     if any(keyword in full_query for keyword in diagnosis_keywords):
#         return QueryType.DIFFERENTIAL_DIAGNOSIS

#     # Default to general query
#     return QueryType.GENERAL_QUERY

# def is_diagnosis_complete(response: str) -> bool:
#     response_lower = response.lower().strip()
#     return "question:" not in response_lower

# def optimize_context_for_llm(context: str) -> str:
#     """ optimization to reduce input tokens."""
#     max_chars = 2500
#     if not context or len(context) <= max_chars:
#         return context
#     return context[:max_chars] + "..."

# @retry(
#     stop=stop_after_attempt(3), 
#     wait=wait_exponential(multiplier=1, min=4, max=10),
#     reraise=True,
#     retry=retry_if_not_exception_type(HTTPException)
# )
# async def generate_response_stream(query: str, chat_history: str, patient_data: str) -> Tuple[str, bool]:
#     """Generate a response using the LLM and retrieved context, with different prompts based on query type."""
#     try:
#         total_start_time = time.time()
#         logger.info("Starting response generation pipeline...")

#         # Step 1: Query Classification
#         classification_start = time.time()
#         query_type = await classify_query(query, patient_data)
#         classification_time = time.time() - classification_start
#         logger.info(f"⚡ Query classification completed in {classification_time:.3f}s - Type: {query_type.value}")

#         # Step 2: Context Retrieval & Optimization
#         retrieval_start = time.time()
#         context, actual_sources = search_all_collections(query, patient_data, k=5)
#         optimized_context = optimize_context_for_llm(context)
#         retrieval_time = time.time() - retrieval_start
#         logger.info(f"📚 Context retrieval & optimization completed in {retrieval_time:.3f}s - Reduced from {len(context)} to {len(optimized_context)} chars")

#         # Step 3: Prompt Preparation
#         sources_text = ", ".join(actual_sources) if actual_sources else "No sources available"

#         if query_type == QueryType.DRUG_INFORMATION:
#             prompt_template = DRUG_INFORMATION_PROMPT
#             temperature = 0.2
#         elif query_type == QueryType.DIFFERENTIAL_DIAGNOSIS:
#             prompt_template = DIFFERENTIAL_DIAGNOSIS_PROMPT
#             temperature = 0.2
#         else:
#             prompt_template = GENERAL_PROMPT
#             temperature = 0.2
            
#         # The dynamic user prompt now includes the full context
#         final_prompt = prompt_template.format(
#             sources=sources_text,
#             context=optimized_context,
#             patient_data=patient_data,
#             chat_history=chat_history or 'No previous conversation'
#         )
        
#         # Step 4: LLM Response Generation
#         llm_start = time.time()
#         model = genai.GenerativeModel("gemini-2.5-flash")

#         stream = await model.generate_content_async(
#             contents=final_prompt,
#             generation_config=genai.types.GenerationConfig(
#                 temperature=temperature,
#                 max_output_tokens=3000,
#                 top_p=0.8,
#                 top_k=20,
#             ),
#             stream=True
#         )

#         first_token_received = False
#         async for chunk in stream:
#             if not first_token_received:
#                 time_to_first_token = time.time() - llm_start
#                 logger.info(f"🤖 Time to first token: {time_to_first_token:.3f}s")
#                 first_token_received = True

#             if chunk.text:
#                 yield chunk.text
        
#         # response_text = response.text
#         # llm_time = time.time() - llm_start
#         # logger.info(f"🤖 LLM response generation completed in {llm_time:.3f}s - Response length: {len(response_text)} chars")

#         total_llm_time = time.time() - llm_start
#         logger.info(f"✅ LLM stream completed in {total_llm_time:.3f}s")
#         total_pipeline_time = time.time() - total_start_time
#         logger.info(f"✅ Entire pipeline (excluding client stream time) finished in {total_pipeline_time:.3f}s")

#         # Step 5: Post-processing
#         # postprocess_start = time.time()
#         # if query_type == QueryType.DRUG_INFORMATION or query_type == QueryType.GENERAL_QUERY:
#         #     diagnosis_complete = True
#         # else:
#         #     diagnosis_complete = is_diagnosis_complete(response_text)
#         # postprocess_time = time.time() - postprocess_start
        
#         # # Final timing summary
#         # total_time = time.time() - total_start_time
#         # logger.info(f"✅ Pipeline completed in {total_time:.3f}s")
#         # logger.info(f"📊 TIMING BREAKDOWN:")
#         # logger.info(f"   ├── Query Classification: {classification_time:.3f}s ({classification_time/total_time*100:.1f}%)")
#         # logger.info(f"   ├── Context Retrieval: {retrieval_time:.3f}s ({retrieval_time/total_time*100:.1f}%)")
#         # logger.info(f"   ├── Prompt Preparation: {prompt_prep_time:.3f}s ({prompt_prep_time/total_time*100:.1f}%)")
#         # logger.info(f"   ├── LLM Generation: {llm_time:.3f}s ({llm_time/total_time*100:.1f}%)")
#         # logger.info(f"   └── Post-processing: {postprocess_time:.3f}s ({postprocess_time/total_time*100:.1f}%)")
        
#         # return response_text, diagnosis_complete
    
#     except exceptions.ResourceExhausted:
#         logger.error("Google API resource exhausted")
#         raise HTTPException(status_code=429, detail="Rate limit exceeded or resource unavailable, please try again later.")
#     except exceptions.GoogleAPIError as e:
#         logger.error(f"Google API error: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Model error: {str(e)}")
#     except Exception as e:
#         logger.error(f"Unexpected error in generate_response: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


import os
import time
import logging
import asyncio
import hashlib
from fastapi import HTTPException
import google.generativeai as genai
from app.services.vectorstore_manager import search_all_collections
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
from dotenv import load_dotenv
from typing import AsyncGenerator, Dict, Tuple
from google.api_core import exceptions
from enum import Enum
import concurrent.futures
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
load_dotenv()

MODEL_NAME = "gemini-2.5-flash"

# Configure genai with API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Simple in-memory cache for responses
RESPONSE_CACHE: Dict[str, Tuple[str, datetime]] = {}
CACHE_TTL_MINUTES = 30  # Cache responses for 30 minutes

PROMPT_TOKEN_LIMIT = 16000

class QueryType(Enum):
    DRUG_INFORMATION = "drug_information"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    GENERAL_QUERY = "general_query"

# DIFFERENTIAL_DIAGNOSIS_PROMPT = """
# Expert medical AI. Generate structured clinical assessment using ONLY provided reference materials.
# 
# CRITICAL RULES:
# 1. **Source-Only**: Use only REFERENCE TEXT below. No external knowledge.
# 2. **Age-Appropriate Sources**: Check PATIENT INFO for age.
# 3. **Cite Diverse Sources**: Use 3-4 different documents. Format: [Source: document_name (Page: X)]
# 4. **Complete ALL Sections**: Must include Clinical Overview, Differential Diagnoses (3-5 items), Immediate Workup, Management, and Red Flags. Do not stop early.
# 
# FORMAT (COMPLETE ALL):
# **CLINICAL OVERVIEW**
# [1-2 sentences with citation]
# 
# **DIFFERENTIAL DIAGNOSES**
# 1. **[Diagnosis]** (XX%): [Justification with citation]
# 2. **[Diagnosis]** (XX%): [Justification with different citation]
# 3. **[Diagnosis]** (XX%): [Justification with different citation]
# [Add 4-5 if relevant]
# 
# **IMMEDIATE WORKUP**
# - [Test 1 with citation]
# - [Test 2]
# 
# **MANAGEMENT**
# - [Immediate action with citation]
# - [Treatment with citation]
# 
# **RED FLAGS**
# - [Warning sign with citation]
# 
# Sources: {sources}
# 
# REFERENCE TEXT: 
# {context}
# """

# DRUG_INFORMATION_PROMPT = """
# Expert pharmacology AI for healthcare professionals. Provide drug information using ONLY the reference materials.
# RULES:
# 1. **Source-Only**: Use only `REFERENCE TEXT`. State "Not in knowledge base" if missing.
# 2. **Citations**: Include full source names and URLs when available.
# 3. **Exact Names**: Use drug names exactly as in knowledge base.
# FORMAT:
# **DRUG OVERVIEW**
# [Brief: what it is, active ingredients, primary uses]
# **SIDE EFFECTS** (by frequency if available)
# - Very Common (>1/10): [list]
# - Common (1/100-1/10): [list]
# - Uncommon/Rare: [list]
# **INTERACTIONS**
# [Known interactions or "None documented"]
# **CONTRAINDICATIONS**
# [List or "None documented"]
# **MECHANISM** (if available)
# [Targets, action, pharmacology]
# Sources: {sources}
# REFERENCE TEXT: 
# {context}
# """

# GENERAL_PROMPT = """
# Medical AI assistant with expertise in clinical medicine. Answer medical questions accurately and concisely.

# CRITICAL RULES:
# 1. **Primary Sources**: Prioritize information from `REFERENCE TEXT` when available. If reference text is insufficient or doesn't address the question, use your general medical knowledge.
# 2. **Citations**: When using reference text, cite as [Source: document_name]. When using general knowledge, state [General Medical Knowledge].
# 3. **Age-Appropriate**: Check PATIENT INFO for age. For adults (≥18 years): avoid citing pediatric sources. For children: prefer pediatric sources.
# 4. **Objective Questions (MCQs)**: If the question has answer options (A, B, C, D, etc.):
#    - Identify the CORRECT answer clearly: **(A) [Option text]** or similar
#    - Explain WHY it's correct with clinical reasoning
#    - Briefly explain why other options are incorrect if relevant
# 5. **Clinical Questions**: Provide differential diagnoses, workup, and management as appropriate
# 6. **BREVITY**: Keep response under 500 words. Be direct and clear.

# FORMAT FOR OBJECTIVE QUESTIONS:
# **Correct Answer: (X) [Option text]**

# **Explanation:**
# [Why this answer is correct with clinical reasoning + citation]

# **Why other options are wrong:** (if helpful)
# - Option Y: [Brief reason]

# FORMAT FOR CLINICAL QUESTIONS:
# [1-2 sentences context + citation]

# **[Relevant Heading]:**
# - [Key point with citation]
# - [Key point with citation]

# **[Management/Workup if applicable]:**
# - [Additional info with citation]

# Available Sources: {sources}

# REFERENCE TEXT: 
# {context}
# """

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

1. **PRIMARY KNOWLEDGE SOURCE**
   - ALWAYS PRIORITIZE INFORMATION RETRIEVED FROM `{context}` (REFERENCE TEXTS).
   - WHEN REFERENCE TEXT DOES NOT ADDRESS THE QUESTION SUFFICIENTLY, FALL BACK TO MODEL KNOWLEDGE AND GIVE REFERENCES`.

2. **CITATIONS**
   - Cite as `[Source: document_name or filename.pdf]`.

3. **AGE-SPECIFIC CONTEXT**
   - IF PATIENT AGE < 18 → use pediatric references first.
   - IF PATIENT AGE ≥ 18 → use adult guidelines and avoid pediatric sources.

4. **MCQ / OBJECTIVE QUESTION HANDLING**
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

5. **CLINICAL / OPEN QUESTIONS HANDLING**
- PROVIDE A STRUCTURED RESPONSE USING THE FOLLOWING FORMAT:

Summary: [Concise context or definition with citation]
Differential Diagnosis (if applicable):

[Condition 1] — [Rationale + citation]

[Condition 2] — [Rationale + citation]

Investigations / Workup:

[Test 1] — [Purpose + citation]

[Test 2] — [Purpose + citation]

Management:

[First-line approach + citation]

[Alternative options + citation]

References: [List all sources used]

6. **FALLBACK BEHAVIOR**
- IF RETRIEVED KNOWLEDGE BASE `{context}` IS EMPTY OR IRRELEVANT:
  - USE INTERNAL MODEL KNOWLEDGE (e.g., Gemini).
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
**REFERENCE TEXT (RAG CONTEXT):** {context}
"""

def optimize_context_for_llm(context: str, max_chars: int = 1200) -> str:
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
    
    # full_query = f"{query} {patient_data}".lower().strip()
    # drug_keywords = ["side effects of", "contraindications for", "dosing of", "interactions of"]
    # if any(keyword in full_query for keyword in drug_keywords):
    #     return QueryType.DRUG_INFORMATION
    # diagnosis_keywords = ["differential diagnosis", "ddx", "patient with", "case of", "year-old", "y/o", "presents with"]
    # if any(keyword in full_query for keyword in diagnosis_keywords):
    #     return QueryType.DIFFERENTIAL_DIAGNOSIS
    # return QueryType.GENERAL_QUERY

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
    if len(RESPONSE_CACHE) > 100:
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
async def generate_response_stream(query: str, chat_history: str, patient_data: str) -> AsyncGenerator[str, None]:
    
    total_start_time = time.time()
    full_response_text = ""  # Initialize at outer scope
    
    try:
        # Check cache first (skip for queries with chat history)
        cache_key = None
        if not chat_history or chat_history == "No previous conversation":
            cache_key = _generate_cache_key(query, patient_data)
            cached_response = _get_cached_response(cache_key)
            if cached_response:
                # Stream cached response in chunks for consistent frontend behavior
                chunk_size = 50  # Stream in 50-character chunks
                for i in range(0, len(cached_response), chunk_size):
                    yield cached_response[i:i + chunk_size]
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
                logger.info(f"⚡ Cached response returned in {time.time() - total_start_time:.3f}s")
                return
        
        # ... (Steps 1-3: Classify, Retrieve, Optimize, Prepare)
        query_type = await classify_query(query, patient_data)
        logger.info(f"Query type: {query_type.value}")

        # Reduce k from 5 to 3 for faster search and less context
        context, actual_sources = search_all_collections(query, patient_data, k=5)
        optimized_context = optimize_context_for_llm(context, max_chars=1800)  # Balanced for quality
        logger.info(f"Context optimized: {len(context)} -> {len(optimized_context)} chars")

        sources_text = ", ".join(actual_sources) if actual_sources else "No sources available"
        
        # TEMPORARILY: Always use GENERAL_PROMPT
        prompt_template = GENERAL_PROMPT
        # prompt_map = {
        #     QueryType.DRUG_INFORMATION: DRUG_INFORMATION_PROMPT,
        #     QueryType.DIFFERENTIAL_DIAGNOSIS: DIFFERENTIAL_DIAGNOSIS_PROMPT,
        #     QueryType.GENERAL_QUERY: GENERAL_PROMPT
        # }
        # prompt_template = prompt_map[query_type]
        
        full_prompt = prompt_template.format(sources=sources_text, context=optimized_context)
        full_prompt += f"\n\nQUERY: {query}\n\nPATIENT INFO: {patient_data}\n\nPREVIOUS CONVERSATION: {chat_history or 'No previous conversation'}"
        
        logger.info(f"--- PROMPT SENT TO API (first 500 chars) ---\n{full_prompt[:500]}\n...")

        # Step 4: Generate Content via TRUE ASYNC STREAMING
        llm_start = time.time()
        logger.info(f"Generating response with streaming...")

        model = genai.GenerativeModel(MODEL_NAME)

        try:
            prompt_token_count = model.count_tokens(full_prompt).total_tokens
            logger.info(f"Calculated input prompt token count: {prompt_token_count}")
            if prompt_token_count > PROMPT_TOKEN_LIMIT:
                error_msg = f"Error: Input prompt exceeds token limit ({prompt_token_count}/{PROMPT_TOKEN_LIMIT})."
                logger.error(error_msg)
                yield error_msg
                return
        except Exception as e:
            logger.error(f"Could not count tokens for the prompt: {e}")
            yield "Error: Could not validate the prompt's length."
            return

        logger.info("Generating response with streaming...")
        
        # Configure safety settings to be more permissive for medical content
        safety_settings = {
            genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        }

        try:
            response_stream = await model.generate_content_async(
                contents=full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=3000, 
                    top_p=0.9,
                    top_k=40, 
                    candidate_count=1, 
                ),
                safety_settings=safety_settings,
                stream=True 
            )
        except Exception as e:
            logger.error(f"Failed to initiate stream: {e}", exc_info=True)
            yield f"Failed to start content generation: {str(e)}"
            return
        
        try:
            first_token_received = False
            
            async for chunk in response_stream:
                if not first_token_received:
                    logger.info(f"⚡ First token received in {time.time() - llm_start:.3f}s")
                    first_token_received = True

                if hasattr(chunk, 'text') and chunk.text:
                    full_response_text += chunk.text
                    yield chunk.text

        except StopAsyncIteration:
            logger.error("Stream ended without content - likely blocked by safety filters")
            yield "Content was blocked. Please rephrase your medical query with more clinical terminology."
            
        except Exception as e:
            logger.error(f"Error during streaming: {e}", exc_info=True)
            yield f"An error occurred: {str(e)}"

        # Cache the complete response if applicable
        if cache_key and full_response_text:
            _cache_response(cache_key, full_response_text)
            
        logger.info(f"Total streaming completed in {time.time() - llm_start:.3f}s")
        logger.info(f"Full pipeline completed in {time.time() - total_start_time:.3f}s")

    except Exception as e:
        # Catch any other unexpected errors at the top level
        logger.error(f"FATAL error in generate_response_stream: {e}", exc_info=True)
        yield f"An unexpected error occurred: {str(e)}"