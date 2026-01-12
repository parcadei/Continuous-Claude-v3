"""
Metrics HTTP Server for Continuous-Claude-v3

Provides a simple HTTP server exposing /metrics endpoint for Prometheus scraping.
Can run standalone or be integrated into existing FastAPI/Starlette applications.

Usage (standalone):
    uv run python scripts/core/metrics_server.py

Usage (integrated):
    from scripts.core.metrics_server import metrics_app
    app.mount("/metrics", metrics_app)

Environment:
    METRICS_HOST: Host to bind (default: 0.0.0.0)
    METRICS_PORT: Port to listen on (default: 9090)
    METRICS_AUTH_TOKEN: Optional Bearer token for authentication
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .metrics import (
    generate_metrics,
    get_content_type,
    system,
    metrics_summary,
    _metrics_registry,
)


def create_metrics_app() -> FastAPI:
    """Create the metrics FastAPI application.

    Returns:
        FastAPI app with /metrics endpoint
    """
    app = FastAPI(
        title="Continuous-Claude-v3 Metrics",
        description="Prometheus metrics endpoint for Continuous-Claude-v3",
        version="1.0.0",
        docs_url=None,  # Disable docs for metrics-only app
        redoc_url=None,
    )

    # CORS middleware for cross-origin scraping
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # Store running state
    _running_state = {"running": False, "task": None}

    @app.on_event("startup")
    async def startup():
        _running_state["running"] = True
        # Start background collection task
        _running_state["task"] = asyncio.create_task(_collect_metrics_loop())

    @app.on_event("shutdown")
    async def shutdown():
        _running_state["running"] = False
        if _running_state["task"]:
            _running_state["task"].cancel()
            try:
                await _running_state["task"]
            except asyncio.CancelledError:
                pass

    async def _collect_metrics_loop():
        """Background loop to collect system metrics."""
        while _running_state["running"]:
            try:
                system.collect()
                system.update_uptime()
                await asyncio.sleep(15)  # Collect every 15 seconds
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def verify_auth(request: Request) -> bool:
        """Verify authentication token if configured."""
        token = os.environ.get("METRICS_AUTH_TOKEN")
        if not token:
            return True

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        return auth_header[7:] == token

    @app.get("/metrics")
    async def metrics_endpoint(request: Request) -> Response:
        """Prometheus metrics endpoint."""
        if not verify_auth(request):
            raise HTTPException(status_code=401, detail="Unauthorized")

        try:
            content = generate_metrics()
            return Response(
                content=content,
                media_type=get_content_type(),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/metrics/summary")
    async def metrics_summary_endpoint(request: Request) -> dict[str, Any]:
        """Get summary of registered metrics."""
        if not verify_auth(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return metrics_summary()

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root redirect to metrics."""
        return {
            "service": "Continuous-Claude-v3 Metrics",
            "endpoints": {
                "/metrics": "Prometheus metrics",
                "/metrics/summary": "Metrics summary",
                "/health": "Health check",
            },
        }

    return app


def run_server(host: str | None = None, port: int | None = None):
    """Run the metrics server.

    Args:
        host: Host to bind (default: METRICS_HOST or 0.0.0.0)
        port: Port to listen on (default: METRICS_PORT or 9090)
    """
    host = host or os.environ.get("METRICS_HOST", "0.0.0.0")
    port = port or int(os.environ.get("METRICS_PORT", "9090"))

    app = create_metrics_app()

    print(f"Starting metrics server on {host}:{port}")
    print(f"Metrics available at http://{host}:{port}/metrics")

    uvicorn.run(app, host=host, port=port, log_level="warning")


def main():
    """Main entry point."""
    run_server()


if __name__ == "__main__":
    main()
