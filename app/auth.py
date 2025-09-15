import os
import vertexai
from dotenv import load_dotenv
from google.auth import load_credentials_from_file
import traceback
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GCP_ID")
PROJECT_LOCATION = os.getenv("GCP_LOCATION")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

def initialize_vertexai():
    try:
        logger.info(f"Initializing Vertex AI with project: {PROJECT_ID}, location: {PROJECT_LOCATION}")
        
        if SERVICE_ACCOUNT_FILE:
            logger.info(f"Attempting to load credentials from: {SERVICE_ACCOUNT_FILE}")
            
            if os.path.exists(SERVICE_ACCOUNT_FILE):
                logger.info("Service account file exists, loading credentials...")
                credentials, project_id = load_credentials_from_file(SERVICE_ACCOUNT_FILE)
                vertexai.init(project=PROJECT_ID, location=PROJECT_LOCATION, credentials=credentials)
                logger.info(f"Successfully loaded credentials from file for project: {project_id}")
            else:
                logger.error(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")
                logger.info("Falling back to application default credentials...")
                vertexai.init(project=PROJECT_ID, location=PROJECT_LOCATION)
        else:
            logger.info("No GOOGLE_APPLICATION_CREDENTIALS environment variable set. Using application default credentials.")
            vertexai.init(project=PROJECT_ID, location=PROJECT_LOCATION)
            
        logger.info("Vertex AI initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

initialize_vertexai()
