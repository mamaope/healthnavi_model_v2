import hashlib
import os
import re
import time
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import requests
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from healthnavi.core.constants import (
    EMPIRICO_MEDICAL_KNOWLEDGE,
    RETRIEVE_K_MULTIPLIER,
    RETRIEVE_K_CAP,
)

_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

ENABLE_SPARSE = os.getenv("ENABLE_SPARSE", "true").lower() in {"1", "true", "yes", "y"}

# ---------- helpers ----------

def _expand_query(q: str) -> str:
    q = (q or "").strip()
    if not q:
        return q
    # add clinical framing that matches guideline phrasing
    return f"{q}. management treatment antibiotics dosing IMCI danger signs classification children under 5"


def _keyword_boost_score(text: str, query: str) -> int:
    q = query.lower()
    t = (text or "").lower()
    boosts = 0
    for kw in ["pneumonia", "amoxicillin", "respiratory rate", "chest indrawing", "imci", "danger sign", "ceftriaxone", "gentamicin"]:
        if kw in t:
            boosts += 1
    # also reward matching query terms
    for token in q.split():
        if len(token) >= 4 and token in t:
            boosts += 1
    return boosts

def _rrf_fuse(rank_lists: List[List[str]], k: int, rrf_k: int = 60) -> List[str]:
    """
    Reciprocal Rank Fusion over multiple ranked lists of ids.
    Returns ids sorted by fused score desc.
    """
    scores: Dict[str, float] = {}
    for lst in rank_lists:
        for i, pid in enumerate(lst):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (rrf_k + (i + 1))
    return [pid for pid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)][:k]


def _safe_payload_get(payload: Dict[str, Any], *keys: str, default=None):
    for k in keys:
        if k in payload and payload[k] is not None:
            return payload[k]
    return default


def _normalize_hit(point: qm.ScoredPoint) -> Dict[str, Any]:
    p = point.payload or {}
    # Be tolerant to payload schema differences (your ingestion payload may use different keys)
    text = _safe_payload_get(p, "text", "content", "chunk", "page_text", default="") or ""
    source = _safe_payload_get(p, "source_pdf", "file_path", "source", default="Unknown")
    printed = _safe_payload_get(p, "printed_page_label", "display_page_number", "page_label", default=None)
    pdf_page_index = _safe_payload_get(p, "pdf_page_index", "page_number", "page", default=None)
    section = _safe_payload_get(p, "section", "heading", default=None)

    # Pretty page label
    if printed is None and pdf_page_index is not None:
        page_disp = f"Page {pdf_page_index}"
    elif printed is not None:
        page_disp = str(printed)
    else:
        page_disp = "Unknown page"

    # Normalize roman numerals / odd labels
    raw = str(page_disp).strip().lower() if page_disp else ""
    if raw in {"cli", "cl", "c", "m"}:
        # these are clearly wrong labels in your data; treat as unknown
        page_disp = "Unknown page"
    elif re.fullmatch(r"[ivxlcdm]+", raw):
        # If it looks like roman numerals, keep as Roman Page
        page_disp = raw.upper()  # e.g. 'CLI'

    # Sanity check: printed_page_label sometimes has year (e.g. 2015) not page number
    if isinstance(page_disp, str):
        s = page_disp.strip()
        if s.isdigit() and int(s) > 500:
            page_disp = "Unknown page"

    return {
        "id": str(point.id),
        "score": float(point.score),
        "content": text,
        "file_path": source,
        "display_page_number": page_disp,
        "section": section,
        "raw_payload": p,
    }


# ---------- embedder client ----------

@dataclass
class EmbedderResult:
    dense: Optional[List[float]]
    sparse_indices: Optional[List[int]]
    sparse_values: Optional[List[float]]


class RemoteEmbedder:
    def __init__(self):
        self.base_url = os.getenv("EMBEDDER_URL", "").rstrip("/")
        if not self.base_url:
            raise RuntimeError("EMBEDDER_URL is not set")
        self.timeout_s = float(os.getenv("EMBEDDER_TIMEOUT", "10"))
        self._session = requests.Session()

        # simple in-memory cache
        self._cache: Dict[str, Tuple[float, EmbedderResult]] = {}
        self._cache_ttl = float(os.getenv("EMBEDDER_CACHE_TTL_SEC", "300"))
        self._cache_max = int(os.getenv("EMBEDDER_CACHE_MAX", "500"))

    def embed(self, text: str, want_dense: bool = True, want_sparse: bool = True) -> EmbedderResult:
        text = text.strip()
        if not text:
            return EmbedderResult(None, None, None)

        self._calls = getattr(self, "_calls", 0) + 1
        logger.info(f"EMBED CALL #{self._calls} len={len(text)} want_sparse={want_sparse}")

        now = time.time()
        ck = f"{want_dense}:{want_sparse}:{text.lower()}"
        if ck in self._cache:
            ts, val = self._cache[ck]
            if now - ts < self._cache_ttl:
                return val
            else:
                del self._cache[ck]

        t0 = time.time()
        logger.info(f"EMBED_ENTER want_dense={want_dense} want_sparse={want_sparse} len={len(text)}")

        t_http0 = time.time()
        logger.info("EMBED_HTTP_START")
        resp = self._session.post(
            f"{self.base_url}/embed",
            json={"text": text, "return_dense": want_dense, "return_sparse": want_sparse},
            timeout=self.timeout_s,
        )
        http_ms = int((time.time() - t_http0) * 1000)
        logger.info(f"EMBED_HTTP_DONE http_ms={http_ms} status={resp.status_code}")

        if resp.status_code != 200:
            raise RuntimeError(f"Embedder error {resp.status_code}: {resp.text}")

        # parse JSON
        t_json0 = time.time()
        data = resp.json()
        json_ms = int((time.time() - t_json0) * 1000)
        logger.info(f"EMBED_JSON_DONE json_ms={json_ms}")

        total_embed_ms = int((time.time() - t0) * 1000)
        logger.info(f"EMBED_EXIT total_ms={total_embed_ms}")
        self._last_embed_timing = {"http_ms": http_ms, "json_ms": json_ms, "total_ms": total_embed_ms}

        dense = data.get("dense") if want_dense else None
        sparse = data.get("sparse") if want_sparse else None

        out = EmbedderResult(
            dense=dense,
            sparse_indices=(sparse or {}).get("indices"),
            sparse_values=(sparse or {}).get("values"),
        )

        # cache insert + trim
        self._cache[ck] = (now, out)
        if len(self._cache) > self._cache_max:
            # drop oldest ~20%
            for k in list(self._cache.keys())[: max(1, self._cache_max // 5)]:
                self._cache.pop(k, None)

        return out


# ---------- qdrant service ----------

class QdrantHybridService:
    """
    Hybrid retrieval against Qdrant using:
      - named dense vector:  "dense"
      - named sparse vector: "sparse"
    We do 2 searches and RRF-fuse results for robustness.
    """

    def __init__(self):
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
        self.collection_name = os.getenv("QDRANT_COLLECTION", EMPIRICO_MEDICAL_KNOWLEDGE)

        self.dense_name = os.getenv("QDRANT_DENSE_VECTOR_NAME", "dense")
        self.sparse_name = os.getenv("QDRANT_SPARSE_VECTOR_NAME", "sparse")

        self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        self.embedder = RemoteEmbedder()

        logger.info(
            f"QdrantHybridService ready: url={self.qdrant_url}, collection={self.collection_name}, "
            f"dense={self.dense_name}, sparse={self.sparse_name}"
        )

    def ping(self) -> bool:
        try:
            _ = self.client.get_collections()
            return True
        except Exception:
            logger.exception("Qdrant ping failed")
            return False

    def _search_named(self, *, vector_name: str, vector, limit: int) -> List[qm.ScoredPoint]:
        """
        Version-compatible Qdrant search for named vectors.
        Prefers query_points() (modern qdrant-client).
        """
        # Preferred: query_points (new API)
        if hasattr(self.client, "query_points"):
            res = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                using=vector_name,           # named vector
                limit=limit,
                with_payload=True,
            )
            # qdrant-client returns an object with .points
            return list(getattr(res, "points", []) or [])

        # Older fallback: search(...) if present
        if hasattr(self.client, "search"):
            # Try tuple style
            try:
                return self.client.search(
                    collection_name=self.collection_name,
                    query_vector=(vector_name, vector),
                    limit=limit,
                    with_payload=True,
                )
            except Exception:
                # Try vector_name keyword style
                return self.client.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    vector_name=vector_name,
                    limit=limit,
                    with_payload=True,
                )

        raise RuntimeError(
            "Your installed qdrant-client does not support query_points() or search(). "
            "Please upgrade qdrant-client, or use the REST API directly."
        )

    def search_medical_knowledge(
        self,
        dense_query: str,
        k: int = 8,
        sparse_query: Optional[str] = None,
        deep_search: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Returns:
          chunks: [{content, file_path, display_page_number, ...}, ...]
          sources: [unique filenames/sources]
        quick_search (deep_search=False) → dense-only. deep_search=True → dense + sparse when ENABLE_SPARSE.
        """
        k = max(1, int(k))
        retrieve_k = min(RETRIEVE_K_CAP, k * RETRIEVE_K_MULTIPLIER)

        enable_sparse = ENABLE_SPARSE and deep_search

        t0 = time.time()
        emb_t0 = time.time()
        expanded = _expand_query(dense_query)
        emb = self.embedder.embed(expanded, want_dense=True, want_sparse=enable_sparse)
        embed_ms = int((time.time() - emb_t0) * 1000)

        logger.info(
            f"Embedder returned dense_len={len(emb.dense) if emb.dense else None} "
            f"sparse_len={len(emb.sparse_indices) if emb.sparse_indices else None}"
        )

        if not emb.dense:
            logger.warning("No dense embedding produced; returning empty.")
            return [], []

        dense_t0 = time.time()
        try:
            dense_hits = self._search_named(vector_name=self.dense_name, vector=emb.dense, limit=retrieve_k)
        except Exception as e:
            logger.exception(str(e))
            raise
        dense_ms = int((time.time() - dense_t0) * 1000)

        sparse_ms = 0
        sparse_hits: List[qm.ScoredPoint] = []
        if enable_sparse and emb.sparse_indices and emb.sparse_values:
            sparse_t0 = time.time()
            try:
                sparse_vec = qm.SparseVector(indices=emb.sparse_indices, values=emb.sparse_values)
                sparse_hits = self._search_named(vector_name=self.sparse_name, vector=sparse_vec, limit=retrieve_k)
            except Exception as e:
                logger.exception(str(e))
                raise
            sparse_ms = int((time.time() - sparse_t0) * 1000)

        total_ms = int((time.time() - t0) * 1000)
        self.last_timing = {"embed_ms": embed_ms, "dense_ms": dense_ms, "sparse_ms": sparse_ms, "total_ms": total_ms}
        last_embed = getattr(self.embedder, "_last_embed_timing", None)
        if last_embed:
            self.last_timing["embed_http_ms"] = last_embed.get("http_ms")
            self.last_timing["embed_json_ms"] = last_embed.get("json_ms")
        logger.info(f"TIMING embed_ms={embed_ms} dense_ms={dense_ms} sparse_ms={sparse_ms} total_ms={total_ms}")
        logger.info(f"Qdrant hits: dense={len(dense_hits)} sparse={len(sparse_hits)}")

        # Fuse
        dense_ids = [str(p.id) for p in dense_hits]
        sparse_ids = [str(p.id) for p in sparse_hits]
        fused_ids = _rrf_fuse([dense_ids, sparse_ids], k=retrieve_k)

        # Build a lookup for scored points (prefer dense score if same id appears)
        by_id: Dict[str, qm.ScoredPoint] = {}
        for p in dense_hits:
            by_id[str(p.id)] = p
        for p in sparse_hits:
            by_id.setdefault(str(p.id), p)

        fused_points = [by_id[i] for i in fused_ids if i in by_id]

        MIN_SCORE = float(os.getenv("MIN_SCORE_DENSE", "0.30"))
        chunks: List[Dict[str, Any]] = []
        sources_set = set()

        for p in fused_points:
            hit = _normalize_hit(p)
            if hit["score"] < MIN_SCORE:
                continue
            chunks.append(hit)
            sources_set.add(os.path.basename(hit.get("file_path", "Unknown")))

        # Deduplicate exact duplicate headings/content
        seen_text = set()
        deduped = []
        for h in chunks:
            key = hashlib.md5(h["content"].strip().encode()).hexdigest()
            if key in seen_text:
                continue
            seen_text.add(key)
            deduped.append(h)
        chunks = deduped

        # Pneumonia (and similar) query: keep chunks that contain query term or key clinical terms
        q = dense_query.lower()
        if "pneumonia" in q:
            chunks = [
                c for c in chunks
                if "pneumonia" in (c.get("content", "").lower())
                or any(kw in (c.get("content", "").lower()) for kw in ["amoxicillin", "chest indrawing", "fast breathing", "imci"])
            ]

        chunks.sort(key=lambda h: (_keyword_boost_score(h["content"], dense_query), h["score"]), reverse=True)
        chunks = chunks[:k]
        sources_set = set(os.path.basename(h.get("file_path", "Unknown")) for h in chunks)

        return chunks, sorted(list(sources_set))


# single instance used by vectorstore_manager
vectordb_service = QdrantHybridService()
