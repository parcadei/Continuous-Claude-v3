"""Agentica Server - FastAPI host for stateful Agentica agents.

This server provides:
- REST API for querying agents
- State persistence across queries and restarts
- Lazy agent creation on first query
- Memory management for large states

Usage:
    # Start server
    uvicorn scripts.agentica.server:app --reload --port 8765

    # Query an agent
    curl -X POST http://localhost:8765/agent/research/query \
        -H "Content-Type: application/json" \
        -d '{"query": "What is Model Context Protocol?"}'
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from .registry import AGENT_TYPES, get_or_create_agent

app = FastAPI(
    title="Agentica Server",
    description="Stateful agent hosting for Claude Code",
    version="0.1.0"
)


class QueryRequest(BaseModel):
    """Request body for agent queries."""
    query: str
    context: Optional[dict] = None


class QueryResponse(BaseModel):
    """Response from agent query."""
    response: str
    agent_type: str
    state_size: int


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/agent/{agent_type}/query", response_model=QueryResponse)
async def query_agent(agent_type: str, request: QueryRequest):
    """Query an agent by type.

    Creates agent lazily on first query.
    Persists state after each query.
    """
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    try:
        agent = await get_or_create_agent(agent_type)

        # Add query to history
        if hasattr(agent, 'state') and agent.state is not None:
            if "query_history" not in agent.state:
                agent.state["query_history"] = []
            agent.state["query_history"].append(request.query)

        response = await agent.call(str, request.query)

        # Persist state after query
        from .registry import persist_agent_state
        await persist_agent_state(agent_type)

        # State size for monitoring
        from .persistence import get_state_size
        state_size = get_state_size(agent_type)

        return QueryResponse(
            response=response,
            agent_type=agent_type,
            state_size=state_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
