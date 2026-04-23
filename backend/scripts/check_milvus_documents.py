"""
Script to inspect the Milvus/Zilliz vector database: list collections,
total entity count, and the exact documents stored.

Searches for .env in these locations (in order):
  1. Same directory as the script
  2. Current working directory
  3. backend/.env (for project structure)
  4. Project root (parent of backend)

Run: python check_milvus_documents.py

Background run (EC2 / long collections):
  nohup python3 -u check_milvus_documents.py > check_milvus.log 2>&1 &
  tail -f check_milvus.log
"""

import os
import sys
import json
import time

from dotenv import load_dotenv

# Force line-buffered output when running under nohup so tail -f shows logs in real time
try:
    if not os.isatty(sys.stdout.fileno()):
        sys.stdout.reconfigure(line_buffering=True)
except (AttributeError, OSError):
    pass  # Python < 3.7 or non-TTY; use flush=True on prints

# Search for .env in multiple locations
_script_dir = os.path.dirname(os.path.abspath(__file__))
_cwd = os.getcwd()
_backend_root = os.path.abspath(os.path.join(_script_dir, ".."))
_project_root = os.path.abspath(os.path.join(_backend_root, ".."))

_env_candidates = [
    os.path.join(_script_dir, ".env"),      # Same dir as script
    os.path.join(_cwd, ".env"),             # Current working directory
    os.path.join(_backend_root, ".env"),    # backend/.env
    os.path.join(_project_root, ".env"),    # project root
]

_env_loaded = False
for _env_path in _env_candidates:
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        print(f"Loaded .env from: {_env_path}", flush=True)
        _env_loaded = True
        break

if not _env_loaded:
    print(f"Warning: No .env file found. Searched:")
    for p in _env_candidates:
        print(f"  - {p}")

MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "medical_knowledge")


def main():
    if not MILVUS_URI or not MILVUS_TOKEN:
        print("ERROR: MILVUS_URI and MILVUS_TOKEN must be set.")
        print("Put a .env file in the same directory as this script with:")
        print("  MILVUS_URI=https://your-cluster.zillizcloud.com")
        print("  MILVUS_TOKEN=your-token")
        print("  MILVUS_COLLECTION_NAME=medical_knowledge")
        sys.exit(1)

    from pymilvus import connections, Collection, utility

    print("Connecting to Zilliz/Milvus...", flush=True)
    connections.connect(uri=MILVUS_URI, token=MILVUS_TOKEN)

    try:
        # List all collections
        collections = utility.list_collections()
        print(f"\nCollections in cluster: {collections}")

        target_collection = COLLECTION_NAME
        if not utility.has_collection(target_collection):
            print(f"Collection '{target_collection}' does not exist.")
            return

        col = Collection(target_collection)
        col.load()

        # Total entity (row) count
        total_entities = col.num_entities
        print(f"\n{'='*60}")
        print(f"Collection: {target_collection}")
        print(f"{'='*60}")
        print(f"Total vectors (chunks): {total_entities:,}")

        # Show schema
        schema = col.schema
        print(f"\nSchema fields:")
        for field in schema.fields:
            print(f"  - {field.name}: {field.dtype.name}")

        if total_entities == 0:
            print("\nCollection is empty.")
            return

        # Query to get unique documents from payload
        # Schema: id (VARCHAR), embedding (FLOAT_VECTOR), payload (VARCHAR/JSON)
        print(f"\nScanning documents (this may take a while for large collections)...", flush=True)
        print(f"  Total entities to scan: {total_entities:,}", flush=True)
        
        unique_filenames = set()
        sample_payloads = []
        batch_size = 500  # Larger batch = faster; reduce if gRPC size limit hit
        last_id = ""
        total_processed = 0
        max_samples = 5
        start_time = time.time()
        progress_interval = 2000  # Log progress every N records

        while True:
            # Query using id (VARCHAR type)
            if last_id:
                expr = f'id > "{last_id}"'
            else:
                expr = "id != ''"

            try:
                results = col.query(
                    expr=expr,
                    output_fields=["id", "payload"],
                    limit=batch_size
                )
            except Exception as e:
                # If payload is too large, reduce batch size
                if "larger than max" in str(e).lower() and batch_size > 10:
                    batch_size = max(10, batch_size // 2)
                    print(f"  Reducing batch size to {batch_size} due to gRPC limit...", flush=True)
                    continue
                print(f"Query error: {e}", flush=True)
                break

            if not results:
                break

            for result in results:
                try:
                    payload_str = result.get("payload", "{}")
                    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                    
                    # Extract filename/file_path from payload
                    filename = (
                        payload.get("filename") or 
                        payload.get("file_path") or 
                        payload.get("source") or
                        "unknown"
                    )
                    unique_filenames.add(filename)
                    
                    # Collect samples
                    if len(sample_payloads) < max_samples:
                        sample_payloads.append({
                            "id": result.get("id"),
                            "filename": filename,
                            "chunk_text_preview": (payload.get("chunk_text", "") or "")[:100],
                            "page": payload.get("display_page_number") or payload.get("page", "?"),
                        })
                    
                    # Track last ID for pagination
                    last_id = result.get("id", last_id)
                except Exception:
                    last_id = result.get("id", last_id)
                    continue

            total_processed += len(results)

            # Progress update at interval (meaningful for tail -f)
            if total_processed % progress_interval == 0 or len(results) < batch_size:
                elapsed = time.time() - start_time
                rate = total_processed / elapsed if elapsed > 0 else 0
                pct = (total_processed / total_entities * 100) if total_entities else 0
                eta_sec = (total_entities - total_processed) / rate if rate > 0 else 0
                eta_min = eta_sec / 60
                print(
                    f"  Processed {total_processed:,} / {total_entities:,} ({pct:.1f}%) | "
                    f"unique files: {len(unique_filenames)} | "
                    f"rate: {rate:.0f}/s | ETA: {eta_min:.1f} min",
                    flush=True
                )

            if len(results) < batch_size:
                break

        # Results
        print(f"\n{'='*60}", flush=True)
        print(f"RESULTS", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"Total vectors (chunks) scanned: {total_processed:,}", flush=True)
        print(f"Unique documents (by filename): {len(unique_filenames)}", flush=True)
        
        if unique_filenames:
            sorted_filenames = sorted(unique_filenames)
            print(f"\nDocument list ({len(sorted_filenames)} files):")
            print("-" * 40)
            for i, fname in enumerate(sorted_filenames, 1):
                print(f"  {i:3}. {fname}")
        else:
            print("\nNo filenames found in payload data.")

        # Show sample records
        if sample_payloads:
            print(f"\n{'='*60}")
            print(f"SAMPLE RECORDS (first {len(sample_payloads)})")
            print(f"{'='*60}")
            for i, sample in enumerate(sample_payloads, 1):
                print(f"\n[{i}] id: {sample['id']}")
                print(f"    filename: {sample['filename']}")
                print(f"    page: {sample['page']}")
                preview = sample['chunk_text_preview']
                if preview:
                    print(f"    content: {preview!r}...")

    finally:
        connections.disconnect("default")
        print(f"\n{'='*60}", flush=True)
        print("Done.", flush=True)


if __name__ == "__main__":
    main()
