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
from datetime import datetime, timedelta

from healthnavi.core.constants import (
    MODEL_NAME, PROMPT_TOKEN_LIMIT, CACHE_TTL_MINUTES, MAX_CACHE_SIZE,
    DEFAULT_CONTEXT_MAX_CHARS, BALANCED_CONTEXT_MAX_CHARS,
    MAX_RETRY_ATTEMPTS, RETRY_MULTIPLIER, RETRY_MIN_WAIT, RETRY_MAX_WAIT,
    QUICK_SEARCH_PROMPT, DEEP_SEARCH_PROMPT
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
load_dotenv()

# Simple in-memory cache for responses
RESPONSE_CACHE: Dict[str, Tuple[str, datetime]] = {}
    

def optimize_context_for_llm(chunks: list[dict], max_chunks: int = 3) -> str:
    """
    Take only the top most relevant chunks to include in the LLM prompt.
    """
    top_chunks = chunks[:max_chunks]
    context_parts = []
    for chunk in top_chunks:
        file_name = os.path.basename(chunk['file_path'])
        file_name = file_name.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
        pdf_page = chunk.get("display_page_number", "?")
        context_parts.append(f"[SOURCE: {file_name} (Page: {pdf_page})]\n{chunk['content'].strip()}")
    return "\n\n".join(context_parts)

def is_diagnosis_complete(response: str) -> bool:
    return "question:" not in response.lower().strip()


def generate_followup_questions_sync(original_query: str, response: str) -> list[str]:
    """
    Generate 3-4 relevant follow-up questions based on the original query and AI response.
    """
    import re
    client = get_genai_client()
    
    try:
        followup_prompt = f"""Generate 3 follow-up questions for this query:

        Q: {original_query[:200]}

        A: {response[:800]}

        Write 3 questions:"""
        
        logger.info("Generating follow-up questions...")
        
        followup_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[{"role": "user", "parts": [{"text": followup_prompt}]}],
            config={
                "temperature": 0.5,
                "max_output_tokens": 1000,  
                "top_p": 0.9,
                "top_k": 40,
                "candidate_count": 1
            }
        )
        
        logger.info(f"Follow-up response received: {followup_response}")
        
        if followup_response and hasattr(followup_response, 'candidates') and followup_response.candidates:
            candidate = followup_response.candidates[0]
            logger.info(f"Candidate: {candidate}")
            logger.info(f"Finish reason: {getattr(candidate, 'finish_reason', 'unknown')}")
            
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                questions_text = candidate.content.parts[0].text.strip()
                logger.info(f"Raw questions text: {questions_text}")
                
                questions = []
                lines = [q.strip() for q in questions_text.split('\n') if q.strip()]
                
                for line in lines:
                    # Remove numbering/bullets 
                    cleaned = re.sub(r'^[\d.\-*•)\s]+', '', line).strip()
                    
                    # Skip intro/header lines
                    if any(skip in cleaned.lower() for skip in ['follow-up questions', 'here are', 'following questions']):
                        continue
                    
                    # Accept any line that looks like a question (minimum 20 chars for a real question)
                    if cleaned and len(cleaned) > 20:
                        if not cleaned.endswith('?'):
                            cleaned = cleaned.rstrip('.') + '?'
                        questions.append(cleaned)
                        logger.info(f"Parsed question: {cleaned}")
                
                if questions:
                    result = questions[:4]
                    logger.info(f"Returning {len(result)} follow-up questions")
                    return result
            else:
                logger.warning(f"No content parts. Candidate content: {getattr(candidate, 'content', 'none')}")
        else:
            logger.warning(f"No candidates in response")
            
    except Exception as e:
        logger.error(f"Error generating follow-up questions: {e}", exc_info=True)
    
    logger.warning("Could not generate follow-up questions")
    return []


def _generate_cache_key(query: str, patient_data: str, deep_search: bool = False) -> str:
    """Generate a cache key from query and patient data."""
    mode = "deep" if deep_search else "standard"
    combined = f"{query}|{patient_data}|{mode}".lower().strip()
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
async def generate_response(query: str, chat_history: str, patient_data: str, deep_search: bool = False) -> tuple[str, bool, str, list[str]]:
    total_start_time = time.time()
    full_response_text = ""
    actual_sources = []
    try:
        # Check cache first (skip for queries with chat history)
        cache_key = None
        if not chat_history or chat_history == "No previous conversation":
            cache_key = _generate_cache_key(query, patient_data, deep_search)
            cached_response = _get_cached_response(cache_key)
            if cached_response:
                logger.info(f"⚡ Cached response returned in {time.time() - total_start_time:.3f}s")
                diagnosis_complete = is_diagnosis_complete(cached_response)
                prompt_type = "deep_search" if deep_search else "quick_search"
                # Generate follow-up questions even for cached responses
                followup_questions = []
                try:
                    followup_questions = generate_followup_questions_sync(query, cached_response)
                except Exception as e:
                    logger.warning(f"Failed to generate follow-up questions for cached response: {e}")
                return cached_response, diagnosis_complete, prompt_type, followup_questions

        # Adjust chunks and sources based on search type
        # Default to quick search unless explicitly enabled
        if deep_search:
            max_chunks = 20
            max_books = 8
            min_chunks = 10
            min_books = 5
            max_output_tokens = 7000
            prompt_template = DEEP_SEARCH_PROMPT
            prompt_type = "deep_search"
            logger.info("🔍 Using DEEP SEARCH mode")
        else:
            max_chunks = 8
            max_books = 4
            min_chunks = 5
            min_books = 3
            max_output_tokens = 3000
            prompt_template = QUICK_SEARCH_PROMPT
            prompt_type = "quick_search"
        
        context, actual_sources = search_all_collections(
            query, 
            patient_data, 
            max_chunks=max_chunks,
            max_books=max_books,
            min_chunks=min_chunks,
            min_books=min_books
        )
        optimized_context = optimize_context_for_llm(context, max_chunks=max_chunks)
        logger.info(f"Context optimized: {len(context)} chunks -> {len(optimized_context)} chars from {len(actual_sources)} sources")

        sources_text = ", ".join(actual_sources) if actual_sources else "No sources available"

        full_prompt = prompt_template.format(sources=sources_text, context=optimized_context)
        user_context_block = f"""
            ### USER QUESTION:
            {query}

            ### CONTEXT (if provided):
            {patient_data or 'No additional context provided.'}

            ### PREVIOUS CONVERSATION SUMMARY:
            {chat_history or 'No previous conversation.'}
            """
        full_prompt += f"\n\n{user_context_block.strip()}"

        logger.info(f"--- PROMPT SENT TO API (first 500 chars) ---\n{full_prompt[:500]}\n...")

        client = get_genai_client()

        llm_start = time.time()
        logger.info("Generating response from model...")

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
                config={
                    "temperature": 0.2,
                    "max_output_tokens": max_output_tokens,
                    "top_p": 0.95,
                    "top_k": 20,
                    "candidate_count": 1
                }
            )
        except Exception as e:
            logger.error(f"Failed to generate content: {e}", exc_info=True)
            prompt_type = "deep_search" if deep_search else "quick_search"
            return f"⚠️ Failed to generate content: {str(e)}", False, prompt_type, []

        try:
            if response and hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]

                if not (hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts):
                    logger.error("Empty or blocked response (no content parts).")
                    prompt_type = "deep_search" if deep_search else "quick_search"
                    return "⚠️ The content was blocked. Please rephrase your question.", False, prompt_type, []

                full_response_text = candidate.content.parts[0].text.strip()
                finish_reason = getattr(candidate, 'finish_reason', 'UNKNOWN')
                logger.info(f"Response finish reason: {finish_reason}")

                if finish_reason == 'MAX_TOKENS':
                    full_response_text += "\n\n**[Note: The response was truncated due to token limits. Try asking a more specific question.]**"
                elif finish_reason in ['SAFETY', 'RECITATION']:
                    full_response_text += "\n\n**[Note: Some content was filtered for safety or duplication.]**"

            else:
                logger.error("Model returned no candidates or empty response.")
                prompt_type = "deep_search" if deep_search else "quick_search"
                return "⚠️ No valid response was generated. Please try again.", False, prompt_type, []

        except Exception as e:
            logger.error(f"Error processing model output: {e}", exc_info=True)
            prompt_type = "deep_search" if deep_search else "quick_search"
            return f"An error occurred while processing the response: {str(e)}", False, prompt_type, []

        # Cache the response for future use
        if cache_key and full_response_text:
            _cache_response(cache_key, full_response_text)

        logger.info(f"✅ Response generated successfully in {time.time() - llm_start:.3f}s")
        logger.info(f"Full pipeline completed in {time.time() - total_start_time:.3f}s")

        # Determine if diagnosis is complete
        diagnosis_complete = is_diagnosis_complete(full_response_text)
        
        # Generate follow-up questions from the response
        followup_questions = []
        try:
            followup_questions = generate_followup_questions_sync(query, full_response_text)
        except Exception as e:
            logger.warning(f"Failed to generate follow-up questions: {e}")
        
        return full_response_text, diagnosis_complete, prompt_type, followup_questions

    except Exception as e:
        logger.error(f"FATAL error in generate_response: {e}", exc_info=True)
        prompt_type = "deep_search" if deep_search else "quick_search"
        return f"🚨 Unexpected error: {str(e)}", False, prompt_type, []
