"""
Transcription service using OpenAI Whisper for voice-to-text conversion.
"""

import os
import logging
import tempfile
import time
import whisper
import torch
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

WHISPER_MODEL = None
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base.en")  

# Performance tuning parameters
# beam_size: Number of beams for beam search (1-5, lower=faster, 1=greedy)
BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1")) 

# best_of: Number of candidates when sampling (1-5, lower=faster)
BEST_OF = int(os.getenv("WHISPER_BEST_OF", "1"))   

TEMPERATURE = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))  

# Temperature fallback increments for accuracy
TEMPERATURE_INCREMENT = float(os.getenv("WHISPER_TEMPERATURE_INCREMENT", "0.2"))

USE_FP16 = os.getenv("WHISPER_USE_FP16", "true").lower() == "true"

# Initial prompt to set context
INITIAL_PROMPT = os.getenv("WHISPER_INITIAL_PROMPT", "")  


def get_whisper_model():
    """
    Load and cache the Whisper model.
    Lazy loading to avoid loading model at startup.
    """
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        logger.info(f"Loading Whisper model: {MODEL_SIZE}")
        try:
            cache_dir = os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
            whisper_cache = os.path.join(cache_dir, "whisper")
            logger.info(f"Whisper cache directory: {whisper_cache}")
            
            if torch.backends.mps.is_available():
                device = "mps"
                logger.info("M1 GPU (MPS) detected - using GPU acceleration")
            elif torch.cuda.is_available():
                device = "cuda"
                logger.info("CUDA GPU detected")
            else:
                device = "cpu"
                logger.info("Using CPU for inference")
            
            start_time = time.time()
            WHISPER_MODEL = whisper.load_model(MODEL_SIZE, device=device)
            load_time = time.time() - start_time
            logger.info(f"Whisper model '{MODEL_SIZE}' loaded successfully on {device} in {load_time:.2f}s")
            
            # Log model configuration
            logger.info(f"Performance config: beam_size={BEAM_SIZE}, best_of={BEST_OF}, fp16={USE_FP16}")
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    return WHISPER_MODEL


def preload_model():
    """
    Preload the Whisper model during application startup.
    """
    try:
        get_whisper_model()
        return True
    except Exception as e:
        logger.error(f"Failed to preload Whisper model: {e}")
        return False



async def transcribe_audio(
    audio_file_bytes: bytes,
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None
) -> dict:
    """
    Transcribe audio file to text using Whisper
    """
    temp_audio_path = None
    start_time = time.time()
    
    try:
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_file_bytes)
            temp_audio_path = temp_audio.name
        
        file_size_mb = len(audio_file_bytes) / (1024 * 1024)
        logger.info(f"Transcribing audio file: {temp_audio_path} ({file_size_mb:.2f} MB)")
        
        # Get the Whisper model
        model = get_whisper_model()
        
        use_fp16 = USE_FP16
        if model.device.type == "cpu":
            use_fp16 = False  
            logger.debug("FP16 disabled (CPU device)")
        
        transcribe_options = {
            "language": language if language else "en", 
            "fp16": use_fp16,  
            "beam_size": BEAM_SIZE,  
            "best_of": BEST_OF, 
            "temperature": 0.0,  # Fixed temp for speed (no fallback sequence)
            "patience": 1.0,  
            "compression_ratio_threshold": 2.4, 
            "logprob_threshold": -1.0,  
            "no_speech_threshold": 0.7,  # Higher threshold to skip silence faster
            "condition_on_previous_text": False,  # Disabled for speed on short clips
            "verbose": False,
        }
        
        # Add initial prompt if provided or use default
        prompt = initial_prompt or INITIAL_PROMPT
        if prompt:
            transcribe_options["initial_prompt"] = prompt
            logger.debug(f"Using initial prompt: {prompt[:50]}...")
        
        logger.debug(f"Transcribe options: {transcribe_options}")
        
        # Transcribe using the model
        transcription_start = time.time()
        result = model.transcribe(temp_audio_path, **transcribe_options)
        transcription_time = time.time() - transcription_start
        
        total_time = time.time() - start_time
        
        logger.info(
            f"Transcription completed in {transcription_time:.2f}s "
            f"(total: {total_time:.2f}s). "
            f"Text length: {len(result['text'])} chars"
        )
        logger.info(f"Detected language: {result.get('language', 'unknown')}")
        
        if result.get('segments') and len(result['segments']) > 0:
            audio_duration = result['segments'][-1]['end']
            rtf = transcription_time / audio_duration if audio_duration > 0 else 0
            logger.info(f"Real-time factor: {rtf:.2f}x (audio: {audio_duration:.1f}s)")
        
        return {
            "text": result["text"].strip(),
            "language": result.get("language", "unknown"),
            "segments": result.get("segments", []),
            "processing_time": transcription_time,
            "total_time": total_time
        }
        
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise Exception(f"Failed to transcribe audio: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.unlink(temp_audio_path)
                logger.debug(f"Cleaned up temporary file: {temp_audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_audio_path}: {str(e)}")
