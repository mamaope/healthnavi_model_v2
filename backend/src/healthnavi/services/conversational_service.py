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
from typing import Dict, Tuple, AsyncGenerator
from google.api_core import exceptions
from enum import Enum
from datetime import datetime, timedelta

from healthnavi.core.constants import (
    MODEL_NAME, PROMPT_TOKEN_LIMIT, CACHE_TTL_MINUTES, MAX_CACHE_SIZE,
    DEFAULT_CONTEXT_MAX_CHARS, BALANCED_CONTEXT_MAX_CHARS,
    MAX_RETRY_ATTEMPTS, RETRY_MULTIPLIER, RETRY_MIN_WAIT, RETRY_MAX_WAIT,
    QUICK_SEARCH_PROMPT, DEEP_SEARCH_PROMPT,
    QUICK_SEARCH_MAX_OUTPUT_TOKENS, DEEP_SEARCH_MAX_OUTPUT_TOKENS,
    CHARS_PER_TOKEN, MAX_CONTEXT_WINDOW, ROLE_INSTRUCTIONS,
    BOLDING_RULES, EXAM_HANDLING, GLOBAL_CONDUCT_RULES
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


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text.
    Rough estimate: ~4 characters per token for English text.
    """
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def validate_prompt_size(prompt: str, max_output_tokens: int, max_input_tokens: int = PROMPT_TOKEN_LIMIT) -> tuple[bool, str, int]:
    """
    Validate that prompt size + output tokens doesn't exceed limits.
    Returns: (is_valid, warning_message, estimated_input_tokens)
    """
    estimated_input_tokens = estimate_tokens(prompt)
    total_tokens = estimated_input_tokens + max_output_tokens
    
    if total_tokens > MAX_CONTEXT_WINDOW:
        return False, f"Total tokens ({total_tokens}) exceeds model context window ({MAX_CONTEXT_WINDOW})", estimated_input_tokens
    
    if estimated_input_tokens > max_input_tokens:
        return False, f"Input prompt tokens ({estimated_input_tokens}) exceeds limit ({max_input_tokens})", estimated_input_tokens
    
    if estimated_input_tokens > max_input_tokens * 0.9:  # Warn if >90% of limit
        return True, f"Warning: Prompt is large ({estimated_input_tokens}/{max_input_tokens} tokens, {estimated_input_tokens/max_input_tokens*100:.1f}%)", estimated_input_tokens
    
    return True, "", estimated_input_tokens


def optimize_context_for_llm(chunks: list[dict], max_chunks: int = 3) -> str:
    """
    Take all relevant chunks and bind them structurally to sources.
    Each chunk is numbered and tagged with its source for mechanical grounding.
    """
    context_parts = []
    
    for idx, chunk in enumerate(chunks, 1):
        file_name = os.path.basename(chunk['file_path'])
        file_name = file_name.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
        pdf_page = chunk.get("display_page_number")
        
        # Create numbered, source-tagged chunks
        if pdf_page and str(pdf_page).strip() and str(pdf_page) != "?":
            source_tag = f"[CHUNK {idx} | SOURCE: {file_name} | PAGE: {pdf_page}]"
        else:
            source_tag = f"[CHUNK {idx} | SOURCE: {file_name}]"
        
        context_parts.append(f"{source_tag}\\n{chunk['content'].strip()}")
    
    return "\n\n".join(context_parts)

def is_diagnosis_complete(response: str) -> bool:
    return "question:" not in response.lower().strip()


def generate_followup_questions_sync(original_query: str, response: str) -> list[str]:
    """
    Generate 3-4 relevant follow-up questions based on the original query and AI response.
    Returns only the questions, no prefix text.
    """
    import re
    client = get_genai_client()
    
    try:
        # Truncate inputs to keep prompt reasonable
        query_truncated = original_query[:300] if len(original_query) > 300 else original_query
        response_truncated = response[:1000] if len(response) > 1000 else response
        
        followup_prompt = f"""Based on this question and answer, generate exactly 3 follow-up questions.

        Question: {query_truncated}

        Answer: {response_truncated}

        IMPORTANT: Output ONLY the 3 questions, one per line. Do NOT include any prefix text like "Here are" or "Follow-up questions:". Start directly with the first question. Each question should be complete and end with a question mark.

        Format:
        1. [First question?]
        2. [Second question?]
        3. [Third question?]"""
        
        logger.info("Generating follow-up questions...")

        followup_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[{"role": "user", "parts": [{"text": followup_prompt}]}],
            config={
                "temperature": 0.7,
                "max_output_tokens": 2000,  # Increased to prevent MAX_TOKENS cutoff
                "top_p": 0.9,
                "top_k": 40,
                "candidate_count": 1
            }
        )
        
        logger.info(f"Follow-up response received: {followup_response}")
        
        if followup_response and hasattr(followup_response, 'candidates') and followup_response.candidates:
            candidate = followup_response.candidates[0]
            logger.info(f"Candidate: {candidate}")
            finish_reason = getattr(candidate, 'finish_reason', 'unknown')
            logger.info(f"Finish reason: {finish_reason}")
            
            if finish_reason == 'MAX_TOKENS':
                logger.warning("⚠️ Follow-up questions hit MAX_TOKENS limit - response may be incomplete")
            
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                questions_text = candidate.content.parts[0].text.strip()
                logger.info(f"Raw questions text: {questions_text}")
                
                questions = []
                lines = [q.strip() for q in questions_text.split('\n') if q.strip()]
                
                for line in lines:
                    # Remove numbering/bullets (1., 2., 3., -, *, •, etc.)
                    cleaned = re.sub(r'^[\d.\-*•)\s]+', '', line).strip()
                    
                    # Skip intro/header lines (more comprehensive check)
                    skip_patterns = [
                        'follow-up questions', 'following questions', 'here are', 
                        'questions:', 'question:', 'based on', 'generated questions',
                        'the questions', 'these questions', 'your questions'
                    ]
                    if any(skip in cleaned.lower() for skip in skip_patterns) and len(cleaned) < 50:
                        continue
                    
                    # Accept any line that looks like a question (minimum 15 chars for a real question)
                    if cleaned and len(cleaned) > 15:
                        # Ensure it ends with ?
                        if not cleaned.endswith('?'):
                            # Remove trailing period/comma and add ?
                            cleaned = re.sub(r'[.,;]+$', '', cleaned).strip() + '?'
                        questions.append(cleaned)
                        logger.info(f"Parsed question: {cleaned}")
                
                if questions:
                    result = questions[:3]  # Return max 3 questions
                    logger.info(f"Returning {len(result)} follow-up questions")
                    return result
                else:
                    logger.warning("No valid questions parsed from response")
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
async def generate_response(query: str, chat_history: str, patient_data: str, deep_search: bool = False, user_role_from_db: str = None) -> tuple[str, bool, str, list[str]]:
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
            max_output_tokens = DEEP_SEARCH_MAX_OUTPUT_TOKENS
            prompt_template = DEEP_SEARCH_PROMPT
            prompt_type = "deep_search"
            logger.info("🔍 Using DEEP SEARCH mode")
        else:
            max_chunks = 8
            max_books = 4
            min_chunks = 5
            min_books = 3
            max_output_tokens = QUICK_SEARCH_MAX_OUTPUT_TOKENS
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

        # Truncate context for quick search to reduce prompt size and improve speed
        if not deep_search and len(optimized_context) > 6000:  # Limit quick search context to 6000 chars
            optimized_context = optimized_context[:6000]

        # Format sources - should always have sources from knowledge base
        if actual_sources and len(actual_sources) > 0:
            sources_text = ", ".join(actual_sources)
            logger.info(f"✅ Sources to be cited ({len(actual_sources)} sources): {sources_text}")
        else:
            # Log as error since this indicates a potential system issue
            logger.error("⚠️ CRITICAL: No sources retrieved from knowledge base! Check vector store connection.")
            sources_text = ""
        
        # Truncate chat history if too long to keep prompt size reasonable
        max_chat_history_chars = 2000  # Limit chat history to ~2000 chars
        truncated_chat_history = chat_history
        if chat_history and len(chat_history) > max_chat_history_chars:
            truncated_chat_history = chat_history[-max_chat_history_chars:]  # Keep last 2000 chars
        
        role_text = get_role_instruction(user_role_from_db)
        full_prompt = prompt_template.format(
            sources=sources_text,
            context=optimized_context,
            role_instruction=role_text,
            bolding_rules=BOLDING_RULES,
            exam_handling=EXAM_HANDLING,
            global_conduct_rules=GLOBAL_CONDUCT_RULES
        )
        user_context_block = f"""
            ### USER QUESTION:
            {query}

            ### CONTEXT (if provided):
            {patient_data or 'No additional context provided.'}

            ### PREVIOUS CONVERSATION SUMMARY:
            {truncated_chat_history or 'No previous conversation.'}
            """
        full_prompt += f"\n\n{user_context_block.strip()}"

        # Validate prompt size before sending
        is_valid, warning_msg, estimated_input_tokens = validate_prompt_size(full_prompt, max_output_tokens)
        if not is_valid:
            logger.error(f"❌ Token limit error: {warning_msg}")
            prompt_type = "deep_search" if deep_search else "quick_search"
            return f"⚠️ Request too large: {warning_msg}. Please try a shorter query or enable deep search.", False, prompt_type, []
        elif warning_msg:
            logger.warning(f"⚠️ {warning_msg}")
        
        logger.info(f"📊 Token estimate - Input: ~{estimated_input_tokens}, Max output: {max_output_tokens}, Total: ~{estimated_input_tokens + max_output_tokens}")
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
                    truncation_note = (
                        f"\n\n---\n"
                        f"**📝 Note:** This response was cut short to keep it concise. "
                        f"If you'd like more detailed information, you can:\n"
                        f"- Ask a follow-up question about a specific part, or\n"
                        f"- Enable **Deep Search** mode for a more comprehensive answer"
                    )
                    full_response_text += truncation_note
                    logger.warning(f"⚠️ Response truncated at {max_output_tokens} tokens. Consider increasing limit or using deep search.")
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


def get_role_instruction(user_role_from_db: str) -> str:
    """Maps the medical_professional_type from the DB to AI prompt instructions."""
    if not user_role_from_db:
        return ROLE_INSTRUCTIONS["DEFAULT"]

    mapping = {
        # EXPERTS
        'Consultant': ROLE_INSTRUCTIONS["EXPERT"],
        'Specialist': ROLE_INSTRUCTIONS["EXPERT"],
        
        # CLINICIANS
        'Senior House Officer': ROLE_INSTRUCTIONS["CLINICIAN"],
        'Senior House Officers': ROLE_INSTRUCTIONS["CLINICIAN"],
        'Medical Officer': ROLE_INSTRUCTIONS["CLINICIAN"],
        'Clinical Officer': ROLE_INSTRUCTIONS["CLINICIAN"],
        'Other Clinical Practitioner': ROLE_INSTRUCTIONS["CLINICIAN"],
        
        'Intern Clinician': ROLE_INSTRUCTIONS["TRAINEE"],
        'Intern Doctor': ROLE_INSTRUCTIONS["TRAINEE"],
        
        'Clinical/Medical Student': ROLE_INSTRUCTIONS["STUDENT"],
        'Student': ROLE_INSTRUCTIONS["STUDENT"]
    }
    
    return mapping.get(user_role_from_db, ROLE_INSTRUCTIONS["DEFAULT"])

async def generate_response_stream(query: str, chat_history: str, patient_data: str, deep_search: bool = False, user_role_from_db: str = None) -> AsyncGenerator[str, None]:
    """
    Generate a streaming response using the LLM.
    Yields text chunks as they are generated for real-time display.
    Falls back to error message if streaming fails.
    """
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
                # Stream cached response in chunks for consistent frontend behavior
                chunk_size = 50  # Stream in 50-character chunks
                for i in range(0, len(cached_response), chunk_size):
                    yield cached_response[i:i + chunk_size]
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
                logger.info(f"⚡ Cached response streamed in {time.time() - total_start_time:.3f}s")
                
                # Generate and yield follow-up questions for cached responses
                if len(cached_response.strip()) > 10:
                    followup_questions = []
                    try:
                        followup_questions = generate_followup_questions_sync(query, cached_response)
                    except Exception as e:
                        logger.warning(f"Failed to generate follow-up questions for cached response: {e}")
                    
                    if followup_questions:
                        import json
                        followup_json = json.dumps(followup_questions)
                        yield f"\n\n[FOLLOWUP_QUESTIONS]:{followup_json}"
                        logger.info(f"✅ Generated {len(followup_questions)} follow-up questions for cached response")
                    else:
                        logger.warning("⚠️ No follow-up questions generated for cached response")
                
                return

        # Adjust chunks and sources based on search type
        if deep_search:
            max_chunks = 20
            max_books = 8
            min_chunks = 10
            min_books = 5
            max_output_tokens = DEEP_SEARCH_MAX_OUTPUT_TOKENS
            prompt_template = DEEP_SEARCH_PROMPT
            prompt_type = "deep_search"
            logger.info("🔍 Using DEEP SEARCH mode (streaming)")
        else:
            max_chunks = 8
            max_books = 4
            min_chunks = 5
            min_books = 3
            max_output_tokens = QUICK_SEARCH_MAX_OUTPUT_TOKENS
            prompt_template = QUICK_SEARCH_PROMPT
            prompt_type = "quick_search"
            logger.info("⚡ Using QUICK SEARCH mode (streaming)")

        # Retrieve context - TIME THIS to identify bottlenecks
        search_start = time.time()
        context, actual_sources = search_all_collections(
            query, 
            patient_data, 
            max_chunks=max_chunks,
            max_books=max_books,
            min_chunks=min_chunks,
            min_books=min_books
        )
        search_time = time.time() - search_start
        logger.info(f"🔍 Vector search completed in {search_time:.3f}s")
        
        optimized_context = optimize_context_for_llm(context, max_chunks=max_chunks)
        logger.info(f"Context optimized: {len(context)} chunks -> {len(optimized_context)} chars from {len(actual_sources)} sources")

        # Truncate context for quick search to reduce prompt size and improve speed
        if not deep_search and len(optimized_context) > 6000:  # Limit quick search context to 6000 chars
            optimized_context = optimized_context[:6000]

        # Format sources
        if actual_sources and len(actual_sources) > 0:
            sources_text = ", ".join(actual_sources)
            logger.info(f"✅ Sources to be cited ({len(actual_sources)} sources): {sources_text}")
        else:
            logger.error("⚠️ CRITICAL: No sources retrieved from knowledge base!")
            sources_text = ""

        # Truncate chat history if too long to keep prompt size reasonable
        max_chat_history_chars = 2000  # Limit chat history to ~2000 chars
        truncated_chat_history = chat_history
        if chat_history and len(chat_history) > max_chat_history_chars:
            truncated_chat_history = chat_history[-max_chat_history_chars:]  # Keep last 2000 chars

        role_text = get_role_instruction(user_role_from_db)
        full_prompt = prompt_template.format(
            sources=sources_text,
            context=optimized_context,
            role_instruction=role_text,
            bolding_rules=BOLDING_RULES,
            exam_handling=EXAM_HANDLING,
            global_conduct_rules=GLOBAL_CONDUCT_RULES
        )
        user_context_block = f"""
            ### USER QUESTION:
            {query}

            ### CONTEXT (if provided):
            {patient_data or 'No additional context provided.'}

            ### PREVIOUS CONVERSATION SUMMARY:
            {truncated_chat_history or 'No previous conversation.'}
            """
        full_prompt += f"\n\n{user_context_block.strip()}"

        # Validate prompt size before sending
        is_valid, warning_msg, estimated_input_tokens = validate_prompt_size(full_prompt, max_output_tokens)
        if not is_valid:
            logger.error(f"❌ Token limit error: {warning_msg}")
            yield f"[STREAM_ERROR]: Request too large: {warning_msg}. Please try a shorter query or enable deep search."
            return
        elif warning_msg:
            logger.warning(f"⚠️ {warning_msg}")
        
        logger.info(f"📊 Token estimate - Input: ~{estimated_input_tokens}, Max output: {max_output_tokens}, Total: ~{estimated_input_tokens + max_output_tokens}")
        logger.info(f"--- STREAMING PROMPT (first 500 chars) ---\n{full_prompt[:500]}\n...")

        client = get_genai_client()

        llm_start = time.time()
        logger.info("Starting streaming response generation...")

        try:
            response_stream = client.models.generate_content_stream(
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

            first_token_received = False
            chunk_count = 0
            finish_reason = None
            final_token_usage = None
            
            try:
                for chunk in response_stream:
                    # Check for finish reason (stream ended) and token usage
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        for candidate in chunk.candidates:
                            if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                                finish_reason = candidate.finish_reason
                                logger.info(f"Stream finished with reason: {finish_reason}")
                    
                    # Capture token usage if available
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        final_token_usage = chunk.usage_metadata
                    elif hasattr(chunk, 'usage') and chunk.usage:
                        final_token_usage = chunk.usage
                    
                    if not first_token_received:
                        ttft = time.time() - llm_start
                        logger.info(f"⚡ First token received in {ttft:.3f}s")
                        first_token_received = True

                    # Extract text from chunk - handle different response formats
                    chunk_text = None
                    
                    if hasattr(chunk, 'text') and chunk.text:
                        chunk_text = chunk.text
                    elif hasattr(chunk, 'candidates') and chunk.candidates:
                        for candidate in chunk.candidates:
                            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        chunk_text = part.text
                                        break
                                if chunk_text:
                                    break
                    elif hasattr(chunk, 'response'):
                        response_obj = chunk.response
                        if hasattr(response_obj, 'candidates') and response_obj.candidates:
                            for candidate in response_obj.candidates:
                                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                                    for part in candidate.content.parts:
                                        if hasattr(part, 'text') and part.text:
                                            chunk_text = part.text
                                            break
                                    if chunk_text:
                                        break
                    
                    if chunk_text:
                        full_response_text += chunk_text
                        chunk_count += 1
                        yield chunk_text
                
                logger.info(f"✅ Streaming completed in {time.time() - llm_start:.3f}s ({chunk_count} chunks, {len(full_response_text)} chars)")
                
                # Log token usage if available
                if final_token_usage:
                    output_tokens = getattr(final_token_usage, 'candidates_token_count', None)
                    if output_tokens:
                        logger.info(f"Token usage - Output: {output_tokens}/{max_output_tokens} tokens ({output_tokens/max_output_tokens*100:.1f}%)")
                
                if finish_reason == 'MAX_TOKENS':
                    truncation_note = (
                        f"\n\n---\n"
                        f"**📝 Note:** This response was cut short to keep it concise. "
                        f"If you'd like more detailed information, you can:\n"
                        f"- Ask a follow-up question about a specific part, or\n"
                        f"- Enable **Deep Search** mode for a more comprehensive answer"
                    )
                    full_response_text += truncation_note
                    yield truncation_note
                    logger.warning(f"⚠️ Response truncated at {max_output_tokens} tokens. Consider increasing limit or using deep search.")
                
                # Warn if stream ended prematurely
                if chunk_count < 10 and finish_reason == 'STOP':
                    logger.warning(f"⚠️ Stream ended with only {chunk_count} text chunks - response may be incomplete")
                    logger.warning(f"   Expected more chunks for a complete response. Check if model is being cut off.")
                elif chunk_count < 5 and not finish_reason:
                    logger.warning(f"⚠️ Stream ended with only {chunk_count} chunks and no finish reason - possible premature termination")
                elif finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS']:
                    logger.warning(f"⚠️ Stream finished with unexpected reason: {finish_reason}")
                
            except Exception as stream_error:
                logger.error(f"Error iterating stream: {stream_error}", exc_info=True)
                raise
            
            logger.info(f"Full pipeline completed in {time.time() - total_start_time:.3f}s")
            logger.info(f"Final response length: {len(full_response_text)} characters")

            # Cache the complete response if applicable
            if cache_key and full_response_text:
                _cache_response(cache_key, full_response_text)

        except Exception as e:
            logger.error(f"Error during streaming: {e}", exc_info=True)
            # Yield error marker that frontend can detect
            yield f"\n\n[STREAM_ERROR]: {str(e)}"

    except Exception as e:
        logger.error(f"FATAL error in generate_response_stream: {e}", exc_info=True)
        yield f"[STREAM_ERROR]: {str(e)}"
