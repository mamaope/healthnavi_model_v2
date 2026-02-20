import os
import re
import sys
import json
import time
import math
import hashlib
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter

from google.longrunning import operations_pb2
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai


# =========================
# CONFIG
# =========================
PROJECT_ID = "regal-autonomy-454806-d1"
LOCATION = "us"
PROCESSOR_ID = "c4a8f6a5f19a3d84"

INPUT_GCS_PREFIX = "gs://empirico_knowledge_base/input/"          # raw PDFs
SPLITS_GCS_PREFIX = "gs://empirico_knowledge_base/splits/"        # split artifacts + page_map
OUTPUT_GCS_PREFIX = "gs://empirico_knowledge_base/docai_out/"     # docAI JSON outputs

PAGES_PER_PART = 450
RUN_DOCAI = True

CHECKPOINT_PATH = "./cdss_pipeline_checkpoint.json"

# =========================
# Printed page label extraction settings
# =========================
ROMAN_RE = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
ARABIC_RE = re.compile(r"^\d{1,5}$")
PAGE_WORD_RE = re.compile(r"(?i)\bpage\s*([0-9]{1,5})\b")


# -------------------------
# Helpers
# -------------------------
def die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def safe_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name[:180]

def sha1_short(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": {}, "running_ops": {}}

def save_checkpoint(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

def gsutil_cp(src: str, dst: str):
    subprocess.check_call(["gsutil", "-q", "cp", src, dst])

def gsutil_ls(prefix: str) -> List[str]:
    out = subprocess.check_output(["gsutil", "ls", prefix], text=True)
    return [l.strip() for l in out.splitlines() if l.strip()]

def gsutil_exists(uri: str) -> bool:
    try:
        subprocess.check_output(["gsutil", "ls", uri], stderr=subprocess.DEVNULL, text=True)
        return True
    except subprocess.CalledProcessError:
        return False

def gsutil_has_any_objects(prefix: str) -> bool:
    # returns True if prefix contains any objects
    try:
        out = subprocess.check_output(["gsutil", "ls", prefix], stderr=subprocess.DEVNULL, text=True)
        return bool(out.strip())
    except subprocess.CalledProcessError:
        return False

def is_pdf_uri(uri: str) -> bool:
    return uri.lower().endswith(".pdf")

def extract_printed_label_from_page(page: fitz.Page) -> Optional[str]:
    rect = page.rect
    W, H = rect.width, rect.height

    regions = [
        fitz.Rect(0, 0, W, H * 0.12),
        fitz.Rect(0, H * 0.88, W, H),
        fitz.Rect(W * 0.30, H * 0.84, W * 0.70, H),
        fitz.Rect(W * 0.30, 0, W * 0.70, H * 0.14),
    ]

    for r in regions:
        txt = page.get_text("text", clip=r).strip()
        if not txt:
            continue
        one = " ".join(txt.split())

        if ARABIC_RE.fullmatch(one):
            return one
        if ROMAN_RE.fullmatch(one):
            return one.lower()

        m = PAGE_WORD_RE.search(one)
        if m:
            return m.group(1)

        tokens = re.findall(r"[A-Za-z0-9]+", one)
        for t in tokens:
            if ARABIC_RE.fullmatch(t):
                return t
            if ROMAN_RE.fullmatch(t):
                return t.lower()

    return None


# -------------------------
# Split metadata
# -------------------------
@dataclass
class PartInfo:
    part_index: int
    start_page: int
    end_page: int
    local_path: str
    gcs_uri: str


def extract_all_page_labels(local_pdf: str) -> Dict[int, Optional[str]]:
    doc = fitz.open(local_pdf)
    page_count = doc.page_count
    labels: Dict[int, Optional[str]] = {}
    for i in range(page_count):
        labels[i + 1] = extract_printed_label_from_page(doc[i])
    doc.close()
    return labels


def split_pdf(local_pdf: str, out_dir: str, base_title: str, pages_per_part: int) -> List[PartInfo]:
    os.makedirs(out_dir, exist_ok=True)
    reader = PdfReader(local_pdf)
    n = len(reader.pages)

    parts: List[PartInfo] = []
    num_parts = math.ceil(n / pages_per_part)

    for p in range(num_parts):
        start = p * pages_per_part
        end = min((p + 1) * pages_per_part, n)  # exclusive
        start_1 = start + 1
        end_1 = end

        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        filename = f"{base_title}__part_{p+1:04d}_p{start_1:04d}-p{end_1:04d}.pdf"
        local_out = os.path.join(out_dir, filename)
        with open(local_out, "wb") as f:
            writer.write(f)

        parts.append(PartInfo(
            part_index=p + 1,
            start_page=start_1,
            end_page=end_1,
            local_path=local_out,
            gcs_uri="",
        ))

    return parts


def submit_docai_batch(
    client: documentai.DocumentProcessorServiceClient,
    processor_name: str,
    gcs_pdf_uris: List[str],
    output_gcs_uri: str,
) -> str:
    gcs_docs = [documentai.GcsDocument(gcs_uri=u, mime_type="application/pdf") for u in gcs_pdf_uris]

    req = documentai.BatchProcessRequest(
        name=processor_name,
        input_documents=documentai.BatchDocumentsInputConfig(
            gcs_documents=documentai.GcsDocuments(documents=gcs_docs)
        ),
        document_output_config=documentai.DocumentOutputConfig(
            gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
                gcs_uri=output_gcs_uri
            )
        ),
    )

    op = client.batch_process_documents(request=req)
    return op.operation.name


def wait_operation(client: documentai.DocumentProcessorServiceClient, op_name: str, poll_s: int = 20):
    ops = client.transport.operations_client
    while True:
        try:
            op = ops.get_operation(op_name)
        except TypeError:
            op = ops.get_operation(operations_pb2.GetOperationRequest(name=op_name))

        if op.done:
            return op
        time.sleep(poll_s)


def main():
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds or not os.path.exists(creds):
        die("Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path (file must exist).")

    checkpoint = load_checkpoint(CHECKPOINT_PATH)

    input_uris = [u for u in gsutil_ls(INPUT_GCS_PREFIX) if is_pdf_uri(u)]
    if not input_uris:
        die(f"No PDFs found under: {INPUT_GCS_PREFIX}")

    docai_client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    )
    processor_name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    print(f"Found {len(input_uris)} PDF(s) under {INPUT_GCS_PREFIX}")
    print(f"Splits -> {SPLITS_GCS_PREFIX}")
    print(f"DocAI out -> {OUTPUT_GCS_PREFIX}")
    print(f"Split threshold/pages per part: {PAGES_PER_PART}")
    print("Resume checkpoint:", CHECKPOINT_PATH)
    print("-" * 80)

    for pdf_uri in input_uris:
        pdf_key = pdf_uri
        base_filename = os.path.basename(pdf_uri)
        base_title = safe_name(os.path.splitext(base_filename)[0])
        doc_tag = f"{base_title}__{sha1_short(pdf_uri)}"
        splits_prefix = SPLITS_GCS_PREFIX.rstrip("/") + f"/{doc_tag}/"
        out_prefix = OUTPUT_GCS_PREFIX.rstrip("/") + f"/{doc_tag}/"

        # ✅ Strong skip rule: if output already exists in GCS, mark complete and skip forever
        if gsutil_has_any_objects(out_prefix):
            checkpoint["done"][pdf_key] = "complete"
            checkpoint["running_ops"].pop(pdf_key, None)
            save_checkpoint(CHECKPOINT_PATH, checkpoint)
            print(f"✅ Skip (output already exists): {pdf_uri}")
            print(f"   Output: {out_prefix}")
            continue

        # Already complete via checkpoint
        if checkpoint["done"].get(pdf_key) == "complete":
            print(f"✅ Skip (already complete in checkpoint): {pdf_uri}")
            continue

        print(f"\n📄 Processing: {pdf_uri}")
        print(f"   doc_tag: {doc_tag}")

        # Resume running operation (if any)
        op_name = checkpoint["running_ops"].get(pdf_key)
        if op_name:
            print("   ↩ Resuming existing operation:", op_name)
            print("   ⏳ Waiting for Document AI to finish...")
            op = wait_operation(docai_client, op_name, poll_s=20)

            if op.error and op.error.message:
                print("   ❌ Document AI error:", op.error.message)
                checkpoint["done"][pdf_key] = "docai_error"
                save_checkpoint(CHECKPOINT_PATH, checkpoint)
                continue

            print("   ✅ Document AI finished.")
            checkpoint["done"][pdf_key] = "complete"
            checkpoint["running_ops"].pop(pdf_key, None)
            save_checkpoint(CHECKPOINT_PATH, checkpoint)
            print(f"✅ Complete: {pdf_uri}")
            print(f"   Output: {out_prefix}")
            continue

        with tempfile.TemporaryDirectory(prefix="cdss_pdf_") as tmp:
            local_pdf = os.path.join(tmp, base_filename)
            local_parts_dir = os.path.join(tmp, "parts")

            print("   ⬇️  Downloading from GCS...")
            gsutil_cp(pdf_uri, local_pdf)

            # Determine page count
            doc = fitz.open(local_pdf)
            page_count = doc.page_count
            doc.close()
            should_split = page_count > PAGES_PER_PART

            print(f"   📄 Pages: {page_count} | split: {should_split}")

            # Always create page_map.json
            print("   🔢 Extracting printed page labels...")
            page_labels = extract_all_page_labels(local_pdf)

            page_map_local = os.path.join(tmp, f"{doc_tag}__page_map.json")
            with open(page_map_local, "w", encoding="utf-8") as f:
                json.dump({
                    "source_pdf_gcs": pdf_uri,
                    "doc_tag": doc_tag,
                    "page_labels_1_based": {str(k): v for k, v in page_labels.items()},
                }, f, indent=2)

            page_map_gcs = splits_prefix + f"{doc_tag}__page_map.json"
            print("   ⬆️  Uploading page_map.json ...")
            gsutil_cp(page_map_local, page_map_gcs)

            gcs_inputs_for_docai: List[str] = []

            if should_split:
                print("   ✂️  Splitting...")
                parts = split_pdf(
                    local_pdf=local_pdf,
                    out_dir=local_parts_dir,
                    base_title=base_title,
                    pages_per_part=PAGES_PER_PART,
                )

                print(f"   ⬆️  Uploading {len(parts)} split part(s)...")
                for p in parts:
                    part_name = os.path.basename(p.local_path)
                    gcs_uri = splits_prefix + part_name
                    gsutil_cp(p.local_path, gcs_uri)
                    p.gcs_uri = gcs_uri
                    gcs_inputs_for_docai.append(gcs_uri)
            else:
                # No split: run DocAI on original PDF directly
                gcs_inputs_for_docai = [pdf_uri]
                print("   ✅ No split needed (DocAI will process original PDF).")

            if RUN_DOCAI:
                print("   🚀 Submitting Document AI batch...")
                op_name = submit_docai_batch(
                    client=docai_client,
                    processor_name=processor_name,
                    gcs_pdf_uris=gcs_inputs_for_docai,
                    output_gcs_uri=out_prefix,
                )
                checkpoint["running_ops"][pdf_key] = op_name
                save_checkpoint(CHECKPOINT_PATH, checkpoint)
                print("   Operation:", op_name)

                print("   ⏳ Waiting for Document AI to finish...")
                op = wait_operation(docai_client, op_name, poll_s=20)

                if op.error and op.error.message:
                    print("   ❌ Document AI error:", op.error.message)
                    checkpoint["done"][pdf_key] = "docai_error"
                    save_checkpoint(CHECKPOINT_PATH, checkpoint)
                    continue

                print("   ✅ Document AI finished.")

        checkpoint["done"][pdf_key] = "complete"
        checkpoint["running_ops"].pop(pdf_key, None)
        save_checkpoint(CHECKPOINT_PATH, checkpoint)

        print(f"✅ Complete: {pdf_uri}")
        print(f"   Page map: {page_map_gcs}")
        print(f"   Output:   {out_prefix}")

    print("\nAll done.")


if __name__ == "__main__":
    main()


# import os, sys
# from google.api_core.client_options import ClientOptions
# from google.cloud import documentai_v1 as documentai

# PROJECT_ID = "regal-autonomy-454806-d1"
# LOCATION = "us"
# PROCESSOR_ID = "c4a8f6a5f19a3d84"

# INPUT_GCS_URI_PREFIX = "gs://empirico_knowledge_base/test_input_ugc/"
# OUTPUT_GCS_URI = "gs://empirico_knowledge_base/test_output_ugc/"

# PAGE_START = 1
# PAGE_END = 10   # start very small

# def die(m):
#     print("ERROR:", m, file=sys.stderr)
#     sys.exit(1)

# def main():
#     creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
#     if not creds or not os.path.exists(creds):
#         die("Set GOOGLE_APPLICATION_CREDENTIALS to your service account json path")

#     client = documentai.DocumentProcessorServiceClient(
#         client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
#     )
#     name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

#     pages = list(range(PAGE_START, PAGE_END + 1))

#     req = documentai.BatchProcessRequest(
#         name=name,
#         input_documents=documentai.BatchDocumentsInputConfig(
#             gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=INPUT_GCS_URI_PREFIX)
#         ),
#         document_output_config=documentai.DocumentOutputConfig(
#             gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
#                 gcs_uri=OUTPUT_GCS_URI
#             )
#         ),
#         process_options=documentai.ProcessOptions(
#             individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
#                 pages=pages
#             )
#         ),
#     )

#     print(f"Submitting Layout Parser batch for pages {PAGE_START}-{PAGE_END}")
#     op = client.batch_process_documents(request=req)
#     print("Operation:", op.operation.name)
#     op.result()
#     print("Done. Check output:", OUTPUT_GCS_URI)

# if __name__ == "__main__":
#     main()


# import os
# import time
# import sys
# import subprocess
# from google.cloud import documentai_v1 as documentai

# PROJECT_ID = "regal-autonomy-454806-d1"
# LOCATION = "us"
# PROCESSOR_ID = "c4a8f6a5f19a3d84"

# INPUT_URI_PREFIX = "gs://empirico_knowledge_base/input/"
# OUTPUT_URI = "gs://empirico_knowledge_base/processed_full/"

# HEARTBEAT_SECONDS = 20

# def die(msg):
#     print(f"ERROR: {msg}", file=sys.stderr)
#     sys.exit(1)

# def count_inputs():
#     # Count PDFs in input bucket
#     cmd = ["gsutil", "ls", f"{INPUT_URI_PREFIX}"]
#     out = subprocess.check_output(cmd, text=True)
#     pdfs = [l for l in out.splitlines() if l.lower().endswith(".pdf")]
#     return len(pdfs)

# def count_outputs():
#     # Count docid markers in output (one per doc)
#     try:
#         out = subprocess.check_output(
#             ["gsutil", "ls", "-r", f"{OUTPUT_URI}**/*.json"],
#             stderr=subprocess.DEVNULL,
#             text=True
#         )
#         return len(out.splitlines())
#     except subprocess.CalledProcessError:
#         return 0

# def main():
#     creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
#     if not creds or not os.path.exists(creds):
#         die("GOOGLE_APPLICATION_CREDENTIALS not set or file missing")

#     total_docs = count_inputs()
#     if total_docs == 0:
#         die("No PDFs found in input folder")

#     print(f"Total input PDFs: {total_docs}")

#     client = documentai.DocumentProcessorServiceClient(
#         client_options={"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
#     )
#     processor_name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

#     request = documentai.BatchProcessRequest(
#         name=processor_name,
#         input_documents=documentai.BatchDocumentsInputConfig(
#             gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=INPUT_URI_PREFIX)
#         ),
#         document_output_config=documentai.DocumentOutputConfig(
#             gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
#                 gcs_uri=OUTPUT_URI
#             )
#         ),
#     )

#     print("\nSubmitting batch job...")
#     operation = client.batch_process_documents(request=request)
#     op_name = operation.operation.name

#     print(f"Operation: {op_name}")
#     print(f"Output: {OUTPUT_URI}")
#     print("Watching progress...\n")

#     start = time.time()
#     last_completed = 0

#     try:
#         while not operation.done():
#             elapsed = time.time() - start
#             completed = count_outputs()

#             rate = completed / max(elapsed / 60.0, 1e-6)  
#             remaining = max(total_docs - completed, 0)
#             eta_minutes = remaining / max(rate, 1e-6)

#             bar_width = 30
#             progress = int((completed / total_docs) * bar_width)
#             bar = "█" * progress + "░" * (bar_width - progress)

#             print(
#                 f"\r[{bar}] {completed}/{total_docs} docs | "
#                 f"{rate:.2f} docs/min | ETA ~ {eta_minutes:.1f} min",
#                 end="",
#                 flush=True
#             )

#             time.sleep(HEARTBEAT_SECONDS)

#         print("\n\nOperation finished.")
#         operation.result(timeout=10)
#         total_time = time.time() - start
#         print(f"Total time: {total_time/60:.1f} minutes")
#         print(f"Results in: {OUTPUT_URI}")

#     except KeyboardInterrupt:
#         print("\n⏸ Stopped watching. Job continues in background.")
#         print("Operation:", op_name)
#     except Exception as e:
#         print("\nOperation ended with error or timed out while fetching result:")
#         print(str(e))
#         print("Operation:", op_name)

# if __name__ == "__main__":
#     main()



# from google.cloud import documentai

# PROJECT_ID = "regal-autonomy-454806-d1"
# LOCATION = "us"
# PROCESSOR_ID = "c4a8f6a5f19a3d84"

# INPUT_URI = "gs://empirico_knowledge_base/input/"
# OUTPUT_URI = "gs://empirico_knowledge_base/processed/"

# client = documentai.DocumentProcessorServiceClient(
#     client_options={"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
# )

# processor_name = client.processor_path(
#     PROJECT_ID, LOCATION, PROCESSOR_ID
# )

# input_config = documentai.BatchDocumentsInputConfig(
#     gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=INPUT_URI)
# )

# output_config = documentai.DocumentOutputConfig(
#     gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
#         gcs_uri=OUTPUT_URI
#     )
# )

# request = documentai.BatchProcessRequest(
#     name=processor_name,
#     input_documents=input_config,
#     document_output_config=output_config,
# )

# operation = client.batch_process_documents(request)

# print("Processing...")

# operation.result()

# print("Done.")
# print("Output:", OUTPUT_URI)


# import os
# import json
# import hashlib
# import time
# from datetime import datetime
# from concurrent.futures import ProcessPoolExecutor, as_completed
# from tqdm import tqdm
# from google.cloud import storage, documentai
# from google.cloud.documentai_v1 import Document
# import gc

# PROJECT_ID = "regal-autonomy-454806-d1"
# LOCATION = "us"
# PROCESSOR_ID = "c4a8f6a5f19a3d84"
# BUCKET_NAME = "empirico_knowledge_base"
# INPUT_PREFIX = "input/"               
# OUTPUT_PREFIX = "processed/"         

# MAX_WORKERS = 12                      
# RATE_LIMIT_SLEEP = 1.0               
# PROCESSED_TRACKER = "processed_pdfs.json"  

# storage_client = storage.Client(project=PROJECT_ID)
# bucket = storage_client.bucket(BUCKET_NAME)
# docai_client = documentai.DocumentProcessorServiceClient(
#     client_options={"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
# )

# PROCESSOR_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

# def load_processed():
#     if os.path.exists(PROCESSED_TRACKER):
#         with open(PROCESSED_TRACKER, 'r') as f:
#             return json.load(f)
#     return {}

# def save_processed(processed):
#     with open(PROCESSED_TRACKER, 'w') as f:
#         json.dump(processed, f, indent=2)

# def get_file_signature(blob):
#     return hashlib.md5(f"{blob.name}{blob.size}{blob.updated}".encode()).hexdigest()

# def process_single_pdf(blob_name):
#     """Worker: process one PDF and upload JSON to GCS processed/ folder"""
#     blob = bucket.blob(blob_name)
    
#     signature = get_file_signature(blob)
#     processed = load_processed()
    
#     if blob_name in processed and processed[blob_name] == signature:
#         return blob_name, True, "skipped (already processed)"

#     print(f"  Processing: {blob_name}")

#     try:
#         pdf_content = blob.download_as_bytes()

#         raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
        
#         request = documentai.ProcessRequest(
#             name=PROCESSOR_NAME,
#             raw_document=raw_document,
#         )
        
#         result = docai_client.process_document(request=request)
#         document = result.document

#         # Build structured output
#         output = {
#             "file_name": blob_name,
#             "processed_at": datetime.utcnow().isoformat(),
#             "pages": []
#         }

#         for page in document.pages:
#             page_data = {
#                 "page_number": page.page_number,
#                 "text": "",
#                 "tables": []
#             }

#             # Plain text
#             for paragraph in page.paragraphs:
#                 page_data["text"] += " ".join([token.text for token in paragraph.layout.text_anchor.text_segments]) + "\n"

#             # Tables → clean Markdown
#             for table in page.tables:
#                 if not table.header_rows:
#                     continue
#                 headers = [cell.text.strip() for cell in table.header_rows[0].cells]
#                 md = "| " + " | ".join(headers) + " |\n"
#                 md += "| " + "---|" * len(headers) + "\n"
#                 for row in table.body_rows:
#                     cells = [cell.text.strip() for cell in row.cells]
#                     md += "| " + " | ".join(cells) + " |\n"
#                 page_data["tables"].append(md.strip())

#             output["pages"].append(page_data)

#         # Save directly to GCS
#         json_name = blob_name.replace(".pdf", ".json").replace(INPUT_PREFIX, OUTPUT_PREFIX)
#         json_blob = bucket.blob(json_name)
#         json_blob.upload_from_string(
#             json.dumps(output, indent=2, ensure_ascii=False),
#             content_type="application/json"
#         )

#         # Mark as done locally
#         processed[blob_name] = signature
#         save_processed(processed)

#         return blob_name, True, f"success → gs://{BUCKET_NAME}/{json_name}"

#     except Exception as e:
#         return blob_name, False, str(e)

# if __name__ == "__main__":
#     print("Starting optimized Document AI batch processing → GCS output")
#     print(f"Bucket: gs://{BUCKET_NAME}")
#     print(f"Input prefix: {INPUT_PREFIX}")
#     print(f"Output prefix: {OUTPUT_PREFIX}")
#     print(f"Workers: {MAX_WORKERS}\n")

#     processed = load_processed()

#     blobs = storage_client.list_blobs(BUCKET_NAME, prefix=INPUT_PREFIX)
#     pdf_blobs = [b.name for b in blobs if b.name.lower().endswith(".pdf")]

#     print(f"Found {len(pdf_blobs)} PDFs\n")

#     success = 0
#     failed = []

#     with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
#         future_to_blob = {
#             executor.submit(process_single_pdf, blob_name): blob_name 
#             for blob_name in pdf_blobs
#         }

#         for future in tqdm(as_completed(future_to_blob), total=len(pdf_blobs), desc="Processing"):
#             blob_name, ok, msg = future.result()
#             if ok:
#                 success += 1
#                 print(f"  {msg}")
#             else:
#                 failed.append((blob_name, msg))
#                 print(f"  FAILED {blob_name}: {msg}")
            
#             time.sleep(RATE_LIMIT_SLEEP)

#     print(f"\nFinished!")
#     print(f"Successfully processed {success}/{len(pdf_blobs)} PDFs")
#     if failed:
#         print(f"Failed: {len(failed)}")
#         for fn, err in failed:
#             print(f"  - {fn}: {err}")

#     print(f"\nResults saved in: gs://{BUCKET_NAME}/{OUTPUT_PREFIX}*.json")
#     print(f"Processed tracker: {PROCESSED_TRACKER} (on this instance)")
