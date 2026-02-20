import os
import time
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# pip install FlagEmbedding fastapi uvicorn[standard]
from FlagEmbedding import BGEM3FlagModel

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("embedder")

MODEL_NAME = os.getenv("EMBEDDER_MODEL", "BAAI/bge-m3")
USE_FP16 = os.getenv("EMBEDDER_FP16", "1") == "1"
DEVICE = os.getenv("EMBEDDER_DEVICE", "cpu")  # cpu is safest for always-on cheap VM
MAX_LEN = int(os.getenv("EMBEDDER_MAX_LEN", "512"))

app = FastAPI(title="HealthNavi Query Embedder", version="1.0.0")

_model: Optional[BGEM3FlagModel] = None


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    return_sparse: bool = True
    return_dense: bool = True


class EmbedResponse(BaseModel):
    model: str
    dense: Optional[List[float]] = None
    sparse: Optional[Dict[str, Any]] = None
    took_ms: int


@app.on_event("startup")
def _startup():
    global _model
    logger.info(f"Loading model: {MODEL_NAME} (fp16={USE_FP16}, device={DEVICE}) ...")
    _model = BGEM3FlagModel(MODEL_NAME, use_fp16=USE_FP16, device=DEVICE)
    logger.info("Model loaded OK.")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    global _model
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    t0 = time.time()
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    try:
        # BGEM3 returns: {"dense_vecs": np.ndarray, "lexical_weights": List[Dict[str,float]]}
        out = _model.encode([text], max_length=MAX_LEN, return_dense=req.return_dense, return_sparse=req.return_sparse)
        dense = None
        sparse = None

        if req.return_dense:
            dense_vec = out["dense_vecs"][0]
            dense = [float(x) for x in dense_vec]

        if req.return_sparse:
            # lexical_weights[0] is a dict: token_id(str) -> weight(float)
            # For Qdrant sparse vectors we want indices(int) and values(float)
            lw = out["lexical_weights"][0] if out.get("lexical_weights") else {}
            # lw keys may be strings; convert to int
            indices = []
            values = []
            for k, v in lw.items():
                try:
                    indices.append(int(k))
                    values.append(float(v))
                except Exception:
                    continue
            sparse = {"indices": indices, "values": values}

        took_ms = int((time.time() - t0) * 1000)
        return EmbedResponse(model=MODEL_NAME, dense=dense, sparse=sparse, took_ms=took_ms)

    except Exception as e:
        logger.exception("Embedding failed")
        raise HTTPException(status_code=500, detail=str(e))
