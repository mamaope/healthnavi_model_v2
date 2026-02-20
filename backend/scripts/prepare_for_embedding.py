"""
Robust chunk builder for Google Document AI Layout Parser outputs.
"""

import os
import re
import sys
import json
import time
import hashlib
import subprocess
from typing import Dict, Any, List, Optional

BUCKET = os.getenv("BUCKET", "empirico_knowledge_base")

DOCAI_OUT_PREFIX = "docai_out/"
SPLITS_PREFIX = "splits/"
CHUNKS_PREFIX = "chunks/"

CHECKPOINT_PATH = "./embedding_prep_checkpoint.json"

FORCE = os.getenv("FORCE", "false").lower() in ("1", "true", "yes", "y")
MAX_JSON_FILES = int(os.getenv("MAX_JSON_FILES", "0"))  

# Chunking controls
TARGET_CHARS = 1400
MAX_CHARS = 2200
MIN_CHARS = 200  

# Table controls
MAX_TABLE_ROWS = 120


# =========================
# Shell helpers
# =========================
def die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_doc_tags": {}}

def save_checkpoint(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

def run_cmd(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True)

def gsutil_ls(uri: str) -> List[str]:
    out = run_cmd(["gsutil", "ls", uri])
    return [l.strip() for l in out.splitlines() if l.strip()]

def gsutil_cat(uri: str) -> str:
    return run_cmd(["gsutil", "cat", uri])

def gsutil_cp(local_path: str, gs_uri: str):
    subprocess.check_call(["gsutil", "-q", "cp", local_path, gs_uri])

def gsutil_exists(gs_uri: str) -> bool:
    try:
        subprocess.check_output(["gsutil", "ls", gs_uri], stderr=subprocess.DEVNULL, text=True)
        return True
    except subprocess.CalledProcessError:
        return False

def sha1_short(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def norm_space(s: str) -> str:
    return " ".join((s or "").split()).strip()

def load_json_from_gcs(gs_uri: str) -> Dict[str, Any]:
    txt = gsutil_cat(gs_uri)
    return json.loads(txt)

def page_map_uri(doc_tag: str) -> str:
    return f"gs://{BUCKET}/{SPLITS_PREFIX}{doc_tag}/{doc_tag}__page_map.json"

def chunks_out_uri(doc_tag: str) -> str:
    return f"gs://{BUCKET}/{CHUNKS_PREFIX}{doc_tag}.jsonl"


# =========================
# Layout Parser extraction
# =========================
def extract_blocks(layout_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns list of normalized blocks:
      {type, page_start, page_end, text}
      {type:'table', page_start, page_end, rows:[[...],[...]]}
    """
    dl = layout_doc.get("documentLayout") or {}
    blocks = dl.get("blocks") or []
    out: List[Dict[str, Any]] = []

    for b in blocks:
        btype = (b.get("type") or "unknown").lower()
        span = b.get("pageSpan") or {}
        page_start = int(span.get("pageStart", 1))
        page_end = int(span.get("pageEnd", page_start))

        # ---- text blocks
        if b.get("textBlock") is not None:
            tb = b.get("textBlock") or {}

            # Case A: tb has direct text
            if tb.get("text"):
                txt = norm_space(tb.get("text", ""))
                if txt:
                    out.append({"type": btype, "page_start": page_start, "page_end": page_end, "text": txt})

            # Case B: nested blocks
            sub = tb.get("blocks") or []
            for sb in sub:
                stb = (sb.get("textBlock") or {})
                t = norm_space(stb.get("text", ""))
                if t:
                    sspan = sb.get("pageSpan") or span
                    out.append({
                        "type": btype,
                        "page_start": int(sspan.get("pageStart", page_start)),
                        "page_end": int(sspan.get("pageEnd", page_end)),
                        "text": t
                    })

        # ---- tables
        if b.get("tableBlock") is not None:
            table = b.get("tableBlock") or {}
            body = table.get("bodyRows") or []
            rows: List[List[str]] = []

            for r in body:
                cells = r.get("cells") or []
                row_vals: List[str] = []
                for c in cells:
                    c_blocks = (c.get("blocks") or [])
                    cell_txt_parts: List[str] = []
                    for cb in c_blocks:
                        ctb = (cb.get("textBlock") or {})
                        t = norm_space(ctb.get("text", ""))
                        if t:
                            cell_txt_parts.append(t)
                    row_vals.append(norm_space(" ".join(cell_txt_parts)))

                if any(v for v in row_vals):
                    rows.append(row_vals)

            if rows:
                out.append({"type": "table", "page_start": page_start, "page_end": page_end, "rows": rows})

    return out


# =========================
# Chunking + table formatting
# =========================
def chunk_text(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= MAX_CHARS:
        return [text]

    # split by double newline (paragraphs)
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: List[str] = []
    cur = ""

    for p in paras:
        if not cur:
            cur = p
            continue

        if len(cur) + 2 + len(p) <= TARGET_CHARS:
            cur += "\n\n" + p
        else:
            chunks.append(cur)
            cur = p

    if cur:
        chunks.append(cur)

    # hard split if still too big
    final: List[str] = []
    for c in chunks:
        if len(c) <= MAX_CHARS:
            final.append(c)
        else:
            for i in range(0, len(c), MAX_CHARS):
                final.append(c[i:i+MAX_CHARS])

    return [c for c in final if c.strip()]


def looks_like_header_row(row: List[str]) -> bool:
    """
    Heuristic: header row tends to be more texty and less numeric,
    and has multiple non-empty cells.
    """
    cells = [norm_space(c) for c in row]
    non_empty = [c for c in cells if c]
    if len(non_empty) < 2:
        return False

    numeric_cells = sum(1 for c in non_empty if re.fullmatch(r"\d+(\.\d+)?", c))
    long_text_cells = sum(1 for c in non_empty if len(c) >= 4 and re.search(r"[A-Za-z]", c))

    # want "mostly text"
    return long_text_cells >= max(1, len(non_empty)//2) and numeric_cells <= len(non_empty)//3


def table_to_kv_text(rows: List[List[str]], max_rows: int = MAX_TABLE_ROWS) -> str:
    """
    Convert table to embedding-friendly text.
    Attempts header->row key:value mapping.
    Falls back to pipe-joined rows if header is not reliable.
    """
    # cleanup
    cleaned = []
    for r in rows:
        rr = [norm_space(c) for c in r]
        if any(rr):
            cleaned.append(rr)
    rows = cleaned[:max_rows]
    if not rows:
        return ""

    # choose header row:
    # 1) if first row looks like header -> use it
    # 2) else try to find a header row in first 5 rows
    header_idx = None
    if looks_like_header_row(rows[0]):
        header_idx = 0
    else:
        for i in range(min(5, len(rows))):
            if looks_like_header_row(rows[i]):
                header_idx = i
                break

    if header_idx is None:
        # fallback pipe format
        lines = []
        for r in rows:
            cells = [c for c in r if c]
            if cells:
                lines.append(" | ".join(cells))
        return "\n".join(lines).strip()

    header = rows[header_idx]
    # make unique headers
    seen = {}
    norm_header = []
    for h in header:
        h2 = h or "COL"
        key = h2.lower()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            h2 = f"{h2}_{seen[key]}"
        norm_header.append(h2)

    body = rows[header_idx + 1 :]
    if not body:
        # no body, just print header row
        return " | ".join([c for c in norm_header if c]).strip()

    out_rows = []
    for r in body:
        pairs = []
        for h, v in zip(norm_header, r):
            if h and v:
                pairs.append(f"{h}: {v}")
        if pairs:
            out_rows.append("Row: " + "; ".join(pairs))

    if not out_rows:
        # fallback
        lines = []
        for r in rows:
            cells = [c for c in r if c]
            if cells:
                lines.append(" | ".join(cells))
        return "\n".join(lines).strip()

    return "\n".join(out_rows).strip()


# =========================
# Main
# =========================
def main():
    ckpt = load_checkpoint(CHECKPOINT_PATH)

    docai_root = f"gs://{BUCKET}/{DOCAI_OUT_PREFIX}"
    doc_tag_prefixes = gsutil_ls(docai_root)
    doc_tags = [u.rstrip("/").split("/")[-1] for u in doc_tag_prefixes if u.rstrip("/").split("/")[-1]]

    if not doc_tags:
        die(f"No doc_tags found under {docai_root}")

    print(f"Found {len(doc_tags)} doc_tag folder(s) in docai_out.")
    print(f"FORCE rebuild: {FORCE}")
    print("-" * 80)

    for doc_tag in doc_tags:
        out_gcs = chunks_out_uri(doc_tag)

        # ✅ strongest skip rule: chunks already exist in bucket
        if not FORCE and gsutil_exists(out_gcs):
            print(f"✅ Skip (chunks already exist): {doc_tag}")
            ckpt["done_doc_tags"][doc_tag] = "complete"
            save_checkpoint(CHECKPOINT_PATH, ckpt)
            continue

        # local checkpoint skip (secondary)
        if not FORCE and ckpt["done_doc_tags"].get(doc_tag) == "complete":
            print(f"✅ Skip (already chunked in checkpoint): {doc_tag}")
            continue

        # Load page_map if present (optional)
        pm_uri = page_map_uri(doc_tag)
        page_map_int: Dict[int, Optional[str]] = {}
        source_pdf = None

        if gsutil_exists(pm_uri):
            pm_full = load_json_from_gcs(pm_uri)
            source_pdf = pm_full.get("source_pdf_gcs")
            page_map = pm_full.get("page_labels_1_based", {}) or {}
            try:
                page_map_int = {int(k): v for k, v in page_map.items()}
            except Exception:
                page_map_int = {}
        else:
            print(f"ℹ️  No page_map.json for {doc_tag} (printed_page_label will be null)")

        # list all json files for this doc_tag
        json_glob = f"gs://{BUCKET}/{DOCAI_OUT_PREFIX}{doc_tag}/**/*.json"
        try:
            json_files = sorted(gsutil_ls(json_glob))
        except subprocess.CalledProcessError:
            json_files = []

        if not json_files:
            print(f"⚠️  No JSON files found for {doc_tag} (skip)")
            ckpt["done_doc_tags"][doc_tag] = "no_json"
            save_checkpoint(CHECKPOINT_PATH, ckpt)
            continue

        if MAX_JSON_FILES > 0:
            json_files = json_files[:MAX_JSON_FILES]

        print(f"\n📦 Building chunks for {doc_tag}")
        print(f"   JSON files: {len(json_files)}")

        # Simple section heuristic
        current_section = None

        out_local = f"/tmp/{doc_tag}__chunks.jsonl"
        total_chunks = 0
        bad_json = 0

        with open(out_local, "w", encoding="utf-8") as out_f:
            for jf in json_files:
                try:
                    doc = load_json_from_gcs(jf)
                except Exception as e:
                    bad_json += 1
                    print(f"   ⚠️  Failed to load {jf}: {e}")
                    continue

                blocks = extract_blocks(doc)

                for b in blocks:
                    btype = (b.get("type") or "unknown").lower()
                    page_start = int(b.get("page_start", 1))
                    page_end = int(b.get("page_end", page_start))
                    printed = page_map_int.get(page_start) if page_map_int else None

                    # update section context
                    if btype in ("header", "heading", "heading-1", "heading-2", "title", "section"):
                        t = norm_space(b.get("text", ""))
                        if t and len(t) <= 220:
                            current_section = t

                    # tables
                    if btype == "table":
                        ttxt = table_to_kv_text(b.get("rows", []))
                        if not ttxt:
                            continue

                        for part in chunk_text(ttxt):
                            if len(part) < 10:
                                continue
                            chunk = {
                                "id": f"{doc_tag}:{sha1_short(jf + str(page_start) + part)}",
                                "doc_tag": doc_tag,
                                "source_pdf": source_pdf,
                                "pdf_page_index": page_start,
                                "pdf_page_end_index": page_end,
                                "printed_page_label": printed,
                                "block_type": "table",
                                "section": current_section,
                                "text": part,
                            }
                            out_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                            total_chunks += 1
                        continue

                    # text blocks
                    txt = norm_space(b.get("text", ""))
                    if not txt:
                        continue

                    for part in chunk_text(txt):
                        if len(part) < MIN_CHARS:
                            # allow smaller if it's clearly a short meaningful sentence/heading
                            if len(part) < 50:
                                continue
                        chunk = {
                            "id": f"{doc_tag}:{sha1_short(jf + str(page_start) + part)}",
                            "doc_tag": doc_tag,
                            "source_pdf": source_pdf,
                            "pdf_page_index": page_start,
                            "pdf_page_end_index": page_end,
                            "printed_page_label": printed,
                            "block_type": btype,
                            "section": current_section,
                            "text": part,
                        }
                        out_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                        total_chunks += 1

        print(f"   ✅ Built {total_chunks} chunks (bad json files: {bad_json})")
        print(f"   ⬆️  Uploading -> {out_gcs}")
        gsutil_cp(out_local, out_gcs)

        ckpt["done_doc_tags"][doc_tag] = "complete"
        save_checkpoint(CHECKPOINT_PATH, ckpt)

    print("\nDone chunking all doc_tags.")


if __name__ == "__main__":
    main()
