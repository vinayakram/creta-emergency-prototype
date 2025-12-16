from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.answer import build_answer
from app.rag.retriever import Retriever


app = FastAPI(title="Creta Emergency Assistant — Prototype v1 (Qdrant)")

origins = [o.strip() for o in (settings.allow_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language emergency description")
    top_k: int | None = Field(None, ge=1, le=10)


class QueryResponse(BaseModel):
    query: str
    steps: list[str]
    warnings: list[str]
    tools: list[str]
    sources: list[dict]
    disclaimer: str


retriever = Retriever()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> dict:
    try:
        top_k = req.top_k or settings.top_k
        chunks = retriever.retrieve(req.query, top_k=top_k)
        if not chunks:
            raise HTTPException(status_code=404, detail="No relevant manual sections found. Did you run ingestion?")
        return build_answer(req.query, chunks)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

PRE_DRIVE_QUERY = (
    "Before starting the vehicle for a long drive, what safety checks and precautions "
    "should be performed to prevent emergency situations while driving?"
)


@app.get("/pre-drive-check", response_model=QueryResponse)
def pre_drive_check() -> dict:
    """
    Proactive safety checklist before starting or during a long drive.
    No user input required.
    """
    try:
        chunks = retriever.retrieve(PRE_DRIVE_QUERY, top_k=settings.top_k,intent="pre_drive",)
        if not chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant manual sections found for pre-drive check.",
            )
        return build_answer(PRE_DRIVE_QUERY, chunks)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))