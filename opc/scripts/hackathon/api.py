#!/usr/bin/env python3
"""Minimal FastAPI for Vercel deployment.

Deploy to Vercel:
    vercel --prod

Usage locally:
    uvicorn scripts.hackathon.api:app --reload --port 8000
"""

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(
    title="CCv3 Hackathon API",
    description="Continuous Context Engineering API",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Models
# ============================================================================

class EmbedRequest(BaseModel):
    text: str
    task: str = "retrieval.passage"


class EmbedResponse(BaseModel):
    embedding: list[float]
    dimension: int
    provider: str


class ChatRequest(BaseModel):
    message: str
    system: str | None = None
    model: str = "fast"


class ChatResponse(BaseModel):
    response: str
    model: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class SearchResponse(BaseModel):
    results: list[dict]
    count: int


class EvalRequest(BaseModel):
    input: str
    output: str
    context: str | None = None


class EvalResponse(BaseModel):
    passed: bool
    scores: dict[str, float]
    failed_metrics: list[str]


class StatusResponse(BaseModel):
    status: str
    providers: dict[str, bool]
    timestamp: str


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {
        "name": "CCv3 Hackathon API",
        "version": "1.0.0",
        "sponsors": ["MongoDB Atlas", "Fireworks AI", "Jina AI", "Galileo"],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
async def status():
    """Check status of all providers."""
    return StatusResponse(
        status="ok",
        providers={
            "mongodb": bool(os.environ.get("MONGODB_URI")),
            "fireworks": bool(os.environ.get("FIREWORKS_API_KEY")),
            "jina": bool(os.environ.get("JINA_API_KEY")),
        },
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    """Generate embedding using Jina v3."""
    from scripts.hackathon.embeddings import Embedder

    embedder = Embedder()
    try:
        embedding = await embedder.embed(req.text, task=req.task)
        return EmbedResponse(
            embedding=embedding,
            dimension=len(embedding),
            provider=embedder._provider,
        )
    finally:
        await embedder.close()


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Chat completion using Fireworks AI."""
    if not os.environ.get("FIREWORKS_API_KEY"):
        raise HTTPException(400, "FIREWORKS_API_KEY not configured")

    from scripts.hackathon.inference import LLM

    llm = LLM(model=req.model)
    try:
        response = await llm.chat(req.message, system=req.system)
        return ChatResponse(response=response, model=llm.model)
    finally:
        await llm.close()


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Search using MongoDB Atlas hybrid search."""
    if not os.environ.get("MONGODB_URI"):
        raise HTTPException(400, "MONGODB_URI not configured")

    from scripts.hackathon.mongo_client import MongoClient
    from scripts.hackathon.embeddings import Embedder

    client = MongoClient()
    embedder = Embedder()

    try:
        await client.connect()
        query_emb = await embedder.embed(req.query, task="retrieval.query")
        results = await client.hybrid_search(req.query, query_emb, limit=req.limit)

        return SearchResponse(
            results=[
                {
                    "id": str(r.get("_id")),
                    "content": r.get("content", ""),
                    "score": r.get("rrf_score", 0),
                }
                for r in results
            ],
            count=len(results),
        )
    finally:
        await client.close()
        await embedder.close()


@app.post("/eval", response_model=EvalResponse)
async def evaluate(req: EvalRequest):
    """Evaluate LLM output quality."""
    from scripts.hackathon.eval_gate import QualityGate

    gate = QualityGate()
    result = await gate.check(req.input, req.output, req.context)

    return EvalResponse(
        passed=result.passed,
        scores=result.scores,
        failed_metrics=result.failed_metrics,
    )


@app.post("/store")
async def store(content: str, metadata: dict = None):
    """Store content in MongoDB Atlas."""
    if not os.environ.get("MONGODB_URI"):
        raise HTTPException(400, "MONGODB_URI not configured")

    from scripts.hackathon.mongo_client import MongoClient
    from scripts.hackathon.embeddings import Embedder

    client = MongoClient()
    embedder = Embedder()

    try:
        await client.connect()
        embedding = await embedder.embed(content)
        doc_id = await client.store(content, embedding=embedding, metadata=metadata)
        return {"id": doc_id, "stored": True}
    finally:
        await client.close()
        await embedder.close()


# ============================================================================
# Vercel handler
# ============================================================================

# For Vercel serverless, export the app
handler = app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
