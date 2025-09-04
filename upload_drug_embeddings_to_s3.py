import os
import sys
import json
import boto3
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.drug_db_service import DrugDatabaseProcessor
from app.services.vectordb_service import embed_fn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def process_and_upload_drug_database():
    """Process drug database and upload embeddings to S3"""
    
    # Configuration
    db_path = "bnf_20210409.db"
    temp_file = f"drug_database_embeddings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    s3_bucket = os.getenv("AWS_S3_BUCKET")
    s3_key = f"output/{temp_file}"  # Same prefix as other embeddings
    
    if not s3_bucket:
        raise ValueError("AWS_S3_BUCKET environment variable not set")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file '{db_path}' not found")
    
    try:
        print("=== Drug Database to S3 Upload Tool ===")
        print(f"Database: {db_path}")
        print(f"S3 Bucket: {s3_bucket}")
        print(f"S3 Key: {s3_key}")
        
        # Step 1: Process database
        print("\n1. Processing drug database...")
        processor = DrugDatabaseProcessor(db_path)
        
        drug_info_list = processor.extract_all_drug_data()
        print(f"   Extracted data for {len(drug_info_list)} drugs")
        
        chunks = processor.create_text_chunks(drug_info_list)
        print(f"   Created {len(chunks)} text chunks")
        
        # Analyze chunk distribution
        chunk_types = {}
        for chunk in chunks:
            chunk_type = chunk["metadata"]["chunk_type"]
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        
        print("   Chunk distribution:")
        for chunk_type, count in chunk_types.items():
            print(f"     {chunk_type}: {count}")
        
        # Step 2: Generate embeddings
        print("\n2. Generating embeddings...")
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        # Generate embeddings in batches to avoid API limits
        batch_size = 50
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            print(f"   Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            try:
                batch_embeddings = embed_fn.embed_documents(batch_texts)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                print(f"   Error in batch {i//batch_size + 1}: {e}")
                raise
        
        print(f"   Generated {len(all_embeddings)} embeddings")
        
        # Step 3: Format data (same format as existing pipeline)
        print("\n3. Formatting data...")
        formatted_data = []
        for text, metadata, embedding in zip(texts, metadatas, all_embeddings):
            formatted_data.append({
                "text": text,
                "metadata": metadata,
                "embeddings": embedding
            })
        
        # Step 4: Save locally first
        print(f"\n4. Saving to local file: {temp_file}")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        file_size_mb = os.path.getsize(temp_file) / (1024 * 1024)
        print(f"   File size: {file_size_mb:.2f} MB")
        
        # Step 5: Upload to S3
        print(f"\n5. Uploading to S3...")
        s3_client = boto3.client('s3')
        
        try:
            s3_client.upload_file(temp_file, s3_bucket, s3_key)
            print(f"   Successfully uploaded to s3://{s3_bucket}/{s3_key}")
        except Exception as e:
            print(f"   Error uploading to S3: {e}")
            raise
        
        # Step 6: Verify upload
        print(f"\n6. Verifying upload...")
        try:
            response = s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
            s3_size_mb = response['ContentLength'] / (1024 * 1024)
            print(f"   S3 file size: {s3_size_mb:.2f} MB")
            print(f"   Upload timestamp: {response['LastModified']}")
        except Exception as e:
            print(f"   Warning: Could not verify upload: {e}")
        
        # Step 7: Cleanup
        print(f"\n7. Cleaning up local file...")
        os.remove(temp_file)
        print(f"   Removed {temp_file}")
        
        print(f"\n=== SUCCESS ===")
        print(f"Drug database embeddings uploaded to S3!")
        print(f"Location: s3://{s3_bucket}/{s3_key}")
        print(f"Total chunks: {len(formatted_data)}")
        print(f"Next step: Restart your application to include drug data in vectorstore")
        
        return s3_key
        
    except Exception as e:
        print(f"\nERROR: {e}")
        # Cleanup on error
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise

def check_existing_drug_data():
    """Check if drug data already exists in S3"""
    
    s3_bucket = os.getenv("AWS_S3_BUCKET")
    if not s3_bucket:
        print("AWS_S3_BUCKET not set")
        return False
    
    try:
        s3_client = boto3.client('s3')
        response = s3_client.list_objects_v2(
            Bucket=s3_bucket, 
            Prefix="output/drug_database_embeddings"
        )
        
        if 'Contents' in response:
            print("Existing drug database files found in S3:")
            for obj in response['Contents']:
                print(f"  {obj['Key']} (Size: {obj['Size']/1024/1024:.2f} MB, Modified: {obj['LastModified']})")
            return True
        else:
            print("No existing drug database files found in S3")
            return False
            
    except Exception as e:
        print(f"Error checking S3: {e}")
        return False

def main():
    """Main function"""
    
    print("=== Drug Database S3 Upload Tool ===")
    
    # Check for existing data
    print("\nChecking for existing drug data in S3...")
    has_existing = check_existing_drug_data()
    
    if has_existing:
        print("\nExisting drug data found. Do you want to:")
        print("1. Continue and create new embeddings (will not overwrite existing)")
        print("2. Exit without changes")
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice != "1":
            print("Exiting without changes.")
            return 0
    
    # Confirm database processing
    print(f"\nThis will:")
    print(f"1. Process the drug database (bnf_20210409.db)")
    print(f"2. Generate embeddings for ~3800+ text chunks")
    print(f"3. Upload to S3 bucket: {os.getenv('AWS_S3_BUCKET')}")
    print(f"4. Enable drug data in your vectorstore")
    
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if not confirm.startswith('y'):
        print("Operation cancelled.")
        return 0
    
    # Process and upload
    try:
        s3_key = process_and_upload_drug_database()
        print(f"\n🎉 SUCCESS! Drug embeddings are now available at: {s3_key}")
        return 0
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 