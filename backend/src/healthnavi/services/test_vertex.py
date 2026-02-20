from google.cloud import discoveryengine_v1 as discoveryengine
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ID = os.getenv("GCP_ID")
LOCATION = os.getenv("VERTEX_AI_SEARCH_LOCATION", "global")
DATA_STORE_ID = os.getenv("VERTEX_AI_SEARCH_DATASTORE_ID")

if not all([PROJECT_ID, LOCATION, DATA_STORE_ID]):
    print("Error: Missing one or more env variables (GCP_ID, VERTEX_AI_SEARCH_LOCATION, VERTEX_AI_SEARCH_DATASTORE_ID)")
    exit(1)

client = discoveryengine.SearchServiceClient()

serving_config = client.serving_config_path(
    project=PROJECT_ID,
    location=LOCATION,
    data_store=DATA_STORE_ID,
    serving_config="default_config"
)

request = discoveryengine.SearchRequest(
    serving_config=serving_config,
    query="pisa medicine dose",           # ← your test query
    page_size=5,                          # number of results/chunks
    content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
        # This is the key change: force full chunk content instead of just snippets
        search_result_mode=discoveryengine.SearchRequest.ContentSearchSpec.SearchResultMode.CHUNKS,
        snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
            return_snippet=True           # still useful as fallback
        )
    )
)

print(f"Searching in data store: {DATA_STORE_ID} (location: {LOCATION})")
print("Query:", request.query)
print("-" * 100)

try:
    response = client.search(request)

    print("=== FULL CHUNKS RETURNED ===\n")
    if not response.results:
        print("No results returned. Possible reasons:")
        print("  - Index still building (wait 5–15 min after import)")
        print("  - Layout Parser not enabled during import")
        print("  - Wrong location / bucket mismatch")
        print("  - PDFs have no extractable text (scanned images only?)")
    else:
        for i, result in enumerate(response.results, 1):
            doc = result.document
            chunk_text = doc.derived_struct_data.get("content", "No content found")
            file_path = doc.derived_struct_data.get("file_path", "Unknown file")
            page = doc.derived_struct_data.get("page_number", "?")
            uri = doc.derived_struct_data.get("uri", "No URI")

            print(f"CHUNK {i}")
            print(f"File     : {file_path}")
            print(f"Page     : {page}")
            print(f"URI      : {uri}")
            print(f"Text preview ({len(chunk_text)} chars total):")
            print(chunk_text[:1500].strip() or "[empty content]")
            print("-" * 100)

except Exception as e:
    print("Search failed:", str(e))
    if "PERMISSION_DENIED" in str(e):
        print("→ Check IAM: your service account needs 'roles/discoveryengine.reader'")
    elif "NOT_FOUND" in str(e):
        print("→ Data store ID or location is wrong — double-check .env")