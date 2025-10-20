import os
import json
import pandas as pd
import logging
import time
from dotenv import load_dotenv
from pymilvus import MilvusClient, DataType
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
MILVUS_URI = os.getenv('MILVUS_URI')
MILVUS_TOKEN = os.getenv('MILVUS_TOKEN')
COLLECTION_NAME = os.getenv('MILVUS_COLLECTION_NAME', 'medical_knowledge')

# Initialize Azure OpenAI client
azure_client = openai.AzureOpenAI(
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('API_VERSION', '2024-02-01')
)
AZURE_DEPLOYMENT = os.getenv('DEPLOYMENT', 'text-embedding-3-large')

class DrugDataIngestion:
    """
    Handles ingestion of processed drug data into Zilliz/Milvus collection
    without affecting existing data.
    """
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.client = None
        
    def connect_to_zilliz(self):
        """Connect to Zilliz/Milvus"""
        try:
            self.client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
            logger.info("Connected to Zilliz successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Zilliz: {e}")
            raise
    
    def check_collection_exists(self):
        """Check if the collection exists and get its info"""
        if not self.client.has_collection(collection_name=COLLECTION_NAME):
            logger.error(f"Collection '{COLLECTION_NAME}' does not exist!")
            raise ValueError(f"Collection '{COLLECTION_NAME}' not found")
        
        # Get collection info
        collection_info = self.client.describe_collection(collection_name=COLLECTION_NAME)
        logger.info(f"Collection '{COLLECTION_NAME}' exists")
        logger.info(f"Collection schema: {collection_info}")
        
        # Get current count
        try:
            stats = self.client.get_collection_stats(collection_name=COLLECTION_NAME)
            current_count = stats.get('row_count', 0)
            logger.info(f"Current collection has {current_count} records")
        except Exception as e:
            logger.warning(f"Could not get collection stats: {e}")
        
        return True
    
    def load_drug_data(self):
        """Load drug data from CSV file"""
        try:
            df = pd.read_csv(self.csv_file_path)
            logger.info(f"Loaded {len(df)} drug records from {self.csv_file_path}")
            
            # Validate required columns
            required_columns = ['drug_id', 'drug_name', 'text_content']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            return df
        except Exception as e:
            logger.error(f"Failed to load drug data: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(openai.RateLimitError),
        before_sleep=before_sleep_log(logger, logging.INFO)
    )
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for a batch of texts using Azure OpenAI.
        """
        logger.info(f"Generating Azure OpenAI embeddings for {len(texts)} texts using deployment '{AZURE_DEPLOYMENT}'...")
        try:
            response = azure_client.embeddings.create(
                input=texts,
                model=AZURE_DEPLOYMENT
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Successfully generated {len(embeddings)} embeddings.")
            return embeddings
        except openai.RateLimitError as e:
            retry_after = e.response.headers.get('Retry-After', 60)
            logger.info(f"Rate limit hit. Retrying after {retry_after} seconds.")
            raise
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def generate_embeddings(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """
        Generates embeddings in batches to respect Azure rate limits.
        """
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"Processing embedding batch {batch_num}/{total_batches} ({len(batch_texts)} texts)...")
            
            embeddings = self.generate_embeddings_batch(batch_texts)
            all_embeddings.extend(embeddings)
            
            # Rate limiting delay
            if batch_num < total_batches:  # Don't sleep after the last batch
                time.sleep(1)
        
        return all_embeddings
    
    def prepare_drug_data_for_insertion(self, df: pd.DataFrame) -> list[dict]:
        """
        Prepare drug data for insertion into Milvus collection.
        Uses a drug-specific file path format to distinguish from other medical documents.
        """
        logger.info("Generating embeddings for drug data...")
        
        # Generate embeddings for all drug text content
        texts = df['text_content'].tolist()
        embeddings = self.generate_embeddings(texts, batch_size=50)  # Smaller batch for drugs
        
        # Prepare data for insertion
        data_to_insert = []
        for idx, (_, row) in enumerate(df.iterrows()):
            # Create a unique file path for each drug that identifies it as drug data
            drug_file_path = f"drugs/bnf_drug_{row['drug_id']}_{row['drug_name'].replace(' ', '_').replace('/', '_')}.drug"
            
            record = {
                "content": row['text_content'],
                "file_path": drug_file_path,
                "display_page_number": str(row['drug_id']),  # Use drug_id as page_number for easy identification
                "vector": embeddings[idx]
            }
            data_to_insert.append(record)
        
        logger.info(f"Prepared {len(data_to_insert)} drug records for insertion")
        return data_to_insert
    
    def check_for_existing_drug_data(self):
        """
        Check if drug data already exists in the collection.
        Returns the count of existing drug records.
        """
        try:
            # Search for existing drug records using the drug file path pattern
            search_result = self.client.query(
                collection_name=COLLECTION_NAME,
                filter='file_path like "drugs/%"',
                output_fields=["file_path"],
                limit=1000  # Adjust if you have more than 1000 drugs
            )
            
            existing_count = len(search_result)
            logger.info(f"Found {existing_count} existing drug records in collection")
            
            if existing_count > 0:
                logger.info(f"Sample existing drug files: {[r['file_path'] for r in search_result[:5]]}")
            
            return existing_count
            
        except Exception as e:
            logger.warning(f"Could not check for existing drug data: {e}")
            return 0
    
    def insert_drug_data(self, data_to_insert: list[dict], batch_size: int = 100):
        """
        Insert drug data into the collection in batches.
        """
        total_batches = (len(data_to_insert) + batch_size - 1) // batch_size
        total_inserted = 0
        
        logger.info(f"Starting insertion of {len(data_to_insert)} drug records in {total_batches} batches")
        
        for i in range(0, len(data_to_insert), batch_size):
            batch = data_to_insert[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            try:
                logger.info(f"Inserting batch {batch_num}/{total_batches} ({len(batch)} records)...")
                
                res = self.client.insert(
                    collection_name=COLLECTION_NAME,
                    data=batch
                )
                
                batch_inserted = res.get('insert_count', len(batch))
                total_inserted += batch_inserted
                
                logger.info(f"Successfully inserted batch {batch_num}: {batch_inserted} records")
                
                # Small delay between batches
                if batch_num < total_batches:
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Failed to insert batch {batch_num}: {e}")
                # Continue with next batch instead of failing completely
                continue
        
        logger.info(f"Drug data insertion complete. Total inserted: {total_inserted}/{len(data_to_insert)}")
        return total_inserted
    
    def verify_insertion(self, expected_count: int):
        """
        Verify that the drug data was inserted correctly.
        """
        try:
            # Count drug records after insertion
            search_result = self.client.query(
                collection_name=COLLECTION_NAME,
                filter='file_path like "drugs/%"',
                output_fields=["file_path"],
                limit=expected_count + 100  # Add buffer
            )
            
            actual_count = len(search_result)
            logger.info(f"Verification: Found {actual_count} drug records in collection")
            
            if actual_count >= expected_count:
                logger.info("✓ Drug data insertion verified successfully")
                return True
            else:
                logger.warning(f"⚠ Expected at least {expected_count} drug records, but found {actual_count}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to verify insertion: {e}")
            return False
    
    def close_connection(self):
        """Close the connection to Zilliz"""
        if self.client:
            self.client.close()
            logger.info("Zilliz connection closed")

def main(csv_file: str = 'comprehensive_drug_data.csv', skip_existing_check: bool = False):
    """
    Main function to ingest drug data into Zilliz collection.
    
    Args:
        csv_file: Path to the CSV file containing processed drug data
        skip_existing_check: If True, skip checking for existing drug data
    """
    logger.info("=== Starting Drug Data Ingestion to Zilliz ===")
    
    # Initialize ingestion handler
    ingestion = DrugDataIngestion(csv_file)
    
    try:
        # Connect to Zilliz
        ingestion.connect_to_zilliz()
        
        # Check if collection exists
        ingestion.check_collection_exists()
        
        # Check for existing drug data (unless skipped)
        if not skip_existing_check:
            existing_count = ingestion.check_for_existing_drug_data()
            if existing_count > 0:
                response = input(f"Found {existing_count} existing drug records. Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    logger.info("Ingestion cancelled by user")
                    return
        
        # Load drug data
        df = ingestion.load_drug_data()
        
        # Prepare data for insertion (includes embedding generation)
        data_to_insert = ingestion.prepare_drug_data_for_insertion(df)
        
        # Insert drug data
        inserted_count = ingestion.insert_drug_data(data_to_insert)
        
        # Verify insertion
        ingestion.verify_insertion(inserted_count)
        
        logger.info("=== Drug Data Ingestion Complete ===")
        logger.info(f"Successfully processed {len(df)} drugs")
        logger.info(f"Successfully inserted {inserted_count} drug records")
        
    except Exception as e:
        logger.error(f"Drug data ingestion failed: {e}")
        raise
    
    finally:
        ingestion.close_connection()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest processed drug data into Zilliz collection")
    parser.add_argument(
        '--csv-file',
        type=str,
        default='comprehensive_drug_data.csv',
        help='Path to the CSV file containing processed drug data'
    )
    parser.add_argument(
        '--skip-existing-check',
        action='store_true',
        help='Skip checking for existing drug data and proceed with insertion'
    )
    
    args = parser.parse_args()
    main(csv_file=args.csv_file, skip_existing_check=args.skip_existing_check)
