import boto3
import os
import json
import time
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from langchain.schema import Document

import app.auth
from app.services.vectordb_service import (
    create_vectorstore, 
    load_vectorstore_from_s3, 
    upload_vectorstore_to_s3,
    is_relevant_content
)

# Load environment variables
load_dotenv()

# Global vectorstore instance
vectorstore = None

def download_large_file_with_retry(s3_client, bucket, key, max_retries=3):
    """Download large S3 file with retry logic."""
    for attempt in range(max_retries):
        try:
            response = s3_client.get_object(Bucket=bucket, Key=key)
            
            # Read in chunks to avoid memory issues
            content = b""
            chunk_size = 1024 * 1024  # 1MB chunks
            
            while True:
                chunk = response['Body'].read(chunk_size)
                if not chunk:
                    break
                content += chunk
            
            # Parse JSON
            data = json.loads(content.decode('utf-8'))
            return data
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                time.sleep(wait_time)
            else:
                raise Exception(f"Failed to download after {max_retries} attempts: {e}")
    
    return None

def process_embedding_batch(batch_data, texts_list, embeddings_list, metadata_list):
    """Process a batch of embedding records efficiently."""
    processed_count = 0
    for record in batch_data:
        text = record.get("text", "").strip()
        metadata = record.get("metadata", {})
        embedding = record.get("embeddings")
        
        if text and embedding and is_relevant_content(text):
            # Ensure consistent metadata structure
            if "source" not in metadata:
                if metadata.get("chunk_type"):  # Drug database format
                    metadata["source"] = "drug_database"
                else:  # PDF format
                    metadata["source"] = metadata.get("filename", "Unknown")
            
            metadata.update({
                "content_length": len(text),
            })
            
            texts_list.append(text)
            metadata_list.append(metadata)
            
            if isinstance(embedding, list):
                embeddings_list.append(embedding)
                processed_count += 1
    
    return processed_count

def get_new_embedding_files():
    """Get list of embedding files that aren't in the current vectorstore."""
    try:
        s3_bucket = os.getenv("AWS_S3_BUCKET")
        if not s3_bucket:
            return []
            
        s3_client = boto3.client('s3')
        
        # Get vectorstore timestamp
        try:
            vectorstore_obj = s3_client.head_object(
                Bucket=s3_bucket, 
                Key="output/vectorstore/vectorstore.tar.gz"
            )
            vectorstore_timestamp = vectorstore_obj['LastModified']
        except Exception:
            # No existing vectorstore - return all files for initial creation
            response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix="output/")
            all_files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.json'):
                        all_files.append({
                            'file': obj['Key'],
                            'timestamp': obj['LastModified'],
                            'size_mb': obj['Size'] / (1024 * 1024),
                            'is_new': True
                        })
            return all_files
        
        # Check for newer embedding files
        response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix="output/")
        
        if 'Contents' not in response:
            return []
            
        new_files = []
        for obj in response['Contents']:
            if obj['Key'].endswith('.json') and obj['LastModified'] > vectorstore_timestamp:
                new_files.append({
                    'file': obj['Key'],
                    'timestamp': obj['LastModified'],
                    'size_mb': obj['Size'] / (1024 * 1024),
                    'is_new': True
                })
        
        return new_files
            
    except Exception as e:
        print(f"Error checking for new files: {e}")
        return []

def add_new_data_to_vectorstore(vectorstore, new_files):
    """Add new embedding data to existing vectorstore."""
    if not new_files:
        return vectorstore
        
    try:
        s3_bucket = os.getenv("AWS_S3_BUCKET")
        s3_client = boto3.client('s3')
        
        new_texts = []
        new_embeddings = []
        new_metadatas = []
        
        # Process each new file
        for file_info in new_files:
            file_key = file_info['file']
            
            try:
                # For large files, use retry logic
                if file_info['size_mb'] > 100:
                    data = download_large_file_with_retry(s3_client, s3_bucket, file_key)
                else:
                    obj = s3_client.get_object(Bucket=s3_bucket, Key=file_key)
                    data = json.load(obj["Body"])
                
                # Process in batches for large files
                if len(data) > 1000:
                    batch_size = 500
                    for i in range(0, len(data), batch_size):
                        batch = data[i:i + batch_size]
                        process_embedding_batch(batch, new_texts, new_embeddings, new_metadatas)
                else:
                    process_embedding_batch(data, new_texts, new_embeddings, new_metadatas)
                
            except Exception as e:
                print(f"Error processing {file_key}: {e}")
                continue
        
        if not new_texts:
            return vectorstore
            
        # Convert new embeddings to numpy
        new_embeddings_np = np.array(new_embeddings, dtype=np.float32)
        
        # Get current document count for new IDs
        current_doc_count = len(vectorstore.docstore._dict)
        
        # Add new embeddings to FAISS index
        vectorstore.index.add(new_embeddings_np)
        
        # Add new documents to docstore
        for i, (text, metadata) in enumerate(zip(new_texts, new_metadatas)):
            doc_id = f"doc_{current_doc_count + i}"
            vectorstore.docstore._dict[doc_id] = Document(
                page_content=text,
                metadata=metadata
            )
            vectorstore.index_to_docstore_id[current_doc_count + i] = doc_id
        
        return vectorstore
        
    except Exception as e:
        print(f"Error adding new data: {e}")
        return vectorstore

def initialize_vectorstore():
    """Initialize the vector store with incremental updates for new data."""
    global vectorstore
    try:        
        if vectorstore is None:
            # Check for new embedding files
            new_files = get_new_embedding_files()
            
            # Try to load existing vectorstore first
            vectorstore = load_vectorstore_from_s3()
            
            if vectorstore and new_files:
                # Incremental update: add only new files
                vectorstore = add_new_data_to_vectorstore(vectorstore, new_files)
                upload_vectorstore_to_s3(vectorstore)
                
            elif not vectorstore:
                # Create new vectorstore from scratch
                vectorstore = create_vectorstore()
                if vectorstore:
                    upload_vectorstore_to_s3(vectorstore)
                else:
                    raise RuntimeError("Failed to create vectorstore")

    except Exception as e:
        print(f"Error during vector store initialization: {e}")
        raise RuntimeError("Failed to initialize vector store.") from e            

def get_vectorstore():
    """Get the initialized vectorstore."""
    if vectorstore is None:
        initialize_vectorstore()
    return vectorstore
