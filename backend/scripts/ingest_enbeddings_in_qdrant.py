import os
import orjson
from tqdm import tqdm
from google.cloud import storage
from qdrant_client import QdrantClient
from qdrant_client.http import models as m

BUCKET = os.getenv("GCS_BUCKET", "empirico_knowledge_base")
EMB_PREFIX = os.getenv("EMB_PREFIX", "embeddings/")
COLLECTION = os.getenv("QDRANT_COLLECTION", "cdss_chunks")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
UPSERT_BATCH = int(os.getenv("UPSERT_BATCH", "128"))

def main():
    q = QdrantClient(url=QDRANT_URL)

    gcs = storage.Client()
    files = [b.name for b in gcs.list_blobs(BUCKET, prefix=EMB_PREFIX) if b.name.endswith(".jsonl")]
    files.sort()
    print(f"Found {len(files)} embedding files under gs://{BUCKET}/{EMB_PREFIX}")

    for name in files:
        print(f"\nIngesting: gs://{BUCKET}/{name}")
        blob = gcs.bucket(BUCKET).blob(name)

        # stream to avoid huge RAM
        points = []
        total = 0
        with blob.open("rb") as f:
            for raw in tqdm(f, desc=os.path.basename(name), unit="pts"):
                if not raw.strip():
                    continue
                obj = orjson.loads(raw)

                pid = obj["point_id"]
                dense = obj["dense"]
                sparse = obj["sparse"]
                payload = obj["payload"]

                pt = m.PointStruct(
                    id=pid,
                    vector={
                        "dense": dense,
                        "sparse": m.SparseVector(indices=sparse["indices"], values=sparse["values"]),
                    },
                    payload=payload,
                )
                points.append(pt)
                total += 1

                if len(points) >= UPSERT_BATCH:
                    q.upsert(collection_name=COLLECTION, points=points)
                    points = []

        if points:
            q.upsert(collection_name=COLLECTION, points=points)

        print(f"✅ Done {name} (upserted ~{total} points)")

if __name__ == "__main__":
    main()
