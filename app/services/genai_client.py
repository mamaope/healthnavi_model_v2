"""
GenAI client initialization module.
This module handles the initialization of the Google GenAI client once at startup.
"""
import os
import logging
from google import genai
from google.genai.types import HttpOptions
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Global client instance
_genai_client = None

def initialize_genai_client():
    """
    Initialize the GenAI client with proper configuration.
    """
    global _genai_client
    
    try:
        # Set environment variables for Vertex AI
        gcp_id = os.getenv("GCP_ID")
        gcp_location = os.getenv("GCP_LOCATION")
        
        if not gcp_id:
            raise ValueError("GCP_ID environment variable is required")
        
        os.environ['GOOGLE_CLOUD_PROJECT'] = gcp_id
        os.environ['GOOGLE_CLOUD_LOCATION'] = gcp_location
        os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'True'
        
        # Initialize the client
        _genai_client = genai.Client(http_options=HttpOptions(api_version="v1"))
        
        logger.info(f"GenAI client initialized successfully for project {gcp_id} in {gcp_location}")
        
    except Exception as e:
        logger.error(f"Failed to initialize GenAI client: {str(e)}")
        raise

def get_genai_client():
    """
    Get the initialized GenAI client.
    """
    global _genai_client
    
    if _genai_client is None:
        raise RuntimeError("GenAI client not initialized. Call initialize_genai_client() first.")
    
    return _genai_client

def is_client_initialized():
    """
    Check if the GenAI client has been initialized.
    """
    global _genai_client
    return _genai_client is not None
