import os
import time
import tempfile
from typing import Any, Dict, List, Tuple, Iterable

import orjson
from tqdm import tqdm
from google.cloud import storage

from FlagEmbedding import BGEM3FlagModel

BUCKET = os.getenv("GCS_BUCKET", "empirico_knowledge_base")
CHUNKS_PREFIX = os.getenv("CHUNKS_PREFIX", "chunks/")          
EMB_PREFIX = os.getenv("EMB_PREFIX", "embeddings/")            
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))               
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "8192"))             
USE_FP16 = os.getenv("USE_FP16", "true").lower() in ("1", "true", "yes")
ENCODE_RETRIES = int(os.getenv("ENCODE_RETRIES", "3"))
ENCODE_RETRY_SLEEP_SEC = float(os.getenv("ENCODE_RETRY_SLEEP_SEC", "2.0"))

LIMIT_FILES = int(os.getenv("LIMIT_FILES", "0"))

# Optional: process only a specific doc_tag (filename without .jsonl)
ONLY_DOC_TAG = os.getenv("ONLY_DOC_TAG", "").strip()


# ----------------------------
# Helpers
# ----------------------------
def to_builtin(x: Any) -> Any:
    """Convert numpy arrays / numpy scalars to built-in Python types for JSON serialization."""
    if hasattr(x, "tolist"):
        return x.tolist()
    return x


def list_chunk_files(gcs: storage.Client) -> List[str]:
    """List input chunk jsonl files under CHUNKS_PREFIX."""
    blobs = list(gcs.list_blobs(BUCKET, prefix=CHUNKS_PREFIX))
    files = [b.name for b in blobs if b.name.endswith(".jsonl")]
    files.sort()
    if ONLY_DOC_TAG:
        target = f"{CHUNKS_PREFIX}{ONLY_DOC_TAG}.jsonl"
        files = [f for f in files if f == target]
    if LIMIT_FILES and LIMIT_FILES > 0:
        files = files[:LIMIT_FILES]
    return files


def gcs_blob_exists(gcs: storage.Client, blob_name: str) -> bool:
    return gcs.bucket(BUCKET).blob(blob_name).exists()


def download_blob_stream(bucket: storage.Bucket, blob_name: str) -> Iterable[bytes]:
    """
    Stream blob content line-by-line without loading everything into RAM.
    We use a file-like reader from the blob and iterate over lines.
    """
    blob = bucket.blob(blob_name)
    with blob.open("rb") as f:
        for line in f:
            yield line


def encode_with_retries(model: BGEM3FlagModel, texts: List[str]) -> Dict[str, Any]:
    """Encode with retry on transient failures."""
    last_err = None
    for attempt in range(1, ENCODE_RETRIES + 1):
        try:
            return model.encode(
                texts,
                batch_size=len(texts),
                max_length=MAX_LENGTH,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
        except Exception as e:
            last_err = e
            if attempt < ENCODE_RETRIES:
                time.sleep(ENCODE_RETRY_SLEEP_SEC * attempt)
            else:
                raise
    raise last_err  # unreachable


def sparse_dict_to_qdrant(sv: Dict[Any, Any]) -> Tuple[List[int], List[float]]:
    """Convert lexical_weights dict to Qdrant sparse format (indices, values)."""
    indices: List[int] = []
    values: List[float] = []
    # sv keys are token ids (often ints); values are floats
    for k, v in sv.items():
        indices.append(int(k))
        values.append(float(v))
    return indices, values


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    gcs = storage.Client()
    bucket = gcs.bucket(BUCKET)

    chunk_files = list_chunk_files(gcs)
    print(f"Found {len(chunk_files)} chunk jsonl files under gs://{BUCKET}/{CHUNKS_PREFIX}")

    print("Loading BGE-M3 model...")
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=USE_FP16)

    for in_name in chunk_files:
        doc_tag = os.path.basename(in_name).replace(".jsonl", "")
        out_name = f"{EMB_PREFIX}{doc_tag}.jsonl"

        if gcs_blob_exists(gcs, out_name):
            print(f"SKIP (already embedded): gs://{BUCKET}/{out_name}")
            continue

        print(f"\nEmbedding: gs://{BUCKET}/{in_name} -> gs://{BUCKET}/{out_name}")

        # Write embeddings to a local temp file (keeps RAM stable)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, prefix=f"{doc_tag}__", suffix=".jsonl") as tmp:
            tmp_path = tmp.name

            batch_records: List[Dict[str, Any]] = []
            batch_texts: List[str] = []

            # Use a progress bar with unknown total (streaming)
            pbar = tqdm(desc=f"{doc_tag}", unit="chunks")

            for raw_line in download_blob_stream(bucket, in_name):
                if not raw_line.strip():
                    continue

                try:
                    rec = orjson.loads(raw_line)
                except Exception:
                    # Skip malformed lines but keep going
                    continue

                text = (rec.get("text") or "").strip()
                if not text:
                    continue

                batch_records.append(rec)
                batch_texts.append(text)

                if len(batch_texts) >= BATCH_SIZE:
                    emb = encode_with_retries(model, batch_texts)
                    dense_vecs = emb["dense_vecs"]
                    sparse_vecs = emb["lexical_weights"]

                    for rec_i, dv, sv in zip(batch_records, dense_vecs, sparse_vecs):
                        dv = to_builtin(dv)  # ✅ FIX: numpy -> list
                        idx, vals = sparse_dict_to_qdrant(sv)

                        out_obj = {
                            "point_id": rec_i["id"],  # stable id from your chunks
                            "dense": dv,
                            "sparse": {"indices": idx, "values": vals},
                            "payload": rec_i,  # keep all fields as payload
                        }
                        tmp.write(orjson.dumps(out_obj) + b"\n")
                        pbar.update(1)

                    batch_records.clear()
                    batch_texts.clear()

            # Flush remaining
            if batch_texts:
                emb = encode_with_retries(model, batch_texts)
                dense_vecs = emb["dense_vecs"]
                sparse_vecs = emb["lexical_weights"]

                for rec_i, dv, sv in zip(batch_records, dense_vecs, sparse_vecs):
                    dv = to_builtin(dv)
                    idx, vals = sparse_dict_to_qdrant(sv)

                    out_obj = {
                        "point_id": rec_i["id"],
                        "dense": dv,
                        "sparse": {"indices": idx, "values": vals},
                        "payload": rec_i,
                    }
                    tmp.write(orjson.dumps(out_obj) + b"\n")
                    pbar.update(1)

            pbar.close()

        # Upload the temp file to GCS
        print(f"Uploading embeddings file to gs://{BUCKET}/{out_name} ...")
        out_blob = bucket.blob(out_name)
        out_blob.upload_from_filename(tmp_path, content_type="application/jsonl")
        print(f"✅ Uploaded embeddings: gs://{BUCKET}/{out_name}")

        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
