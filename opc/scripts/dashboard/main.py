"""Session Dashboard FastAPI application.

Provides real-time session monitoring and management interface.
"""

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.db.postgres_pool import close_pool, get_pool
from dashboard.config import settings, setup_logging
from dashboard.routers.health import router as health_router
from dashboard.routers.handoffs import router as handoffs_router
from dashboard.routers.knowledge import router as knowledge_router
from dashboard.routers.memory import router as memory_router
from dashboard.routers.roadmap import router as roadmap_router
from dashboard.tasks.health_monitor import HealthMonitor
from dashboard.websocket.manager import ConnectionManager

# Setup logging with rotating file handler
setup_logging()

logger = logging.getLogger(__name__)

manager = ConnectionManager()
health_monitor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown.

    On startup: Initialize database connection pool and health monitor
    On shutdown: Close database connection pool and stop health monitor
    """
    global health_monitor

    try:
        await get_pool()
        logger.info("Database pool initialized")
    except Exception as e:
        logger.warning(f"Database pool initialization failed: {e}")

    # Start health monitor
    health_monitor = HealthMonitor(manager)
    asyncio.create_task(health_monitor.start())
    logger.info("Health monitor started")

    yield

    # Stop health monitor
    if health_monitor:
        await health_monitor.stop()
        logger.info("Health monitor stopped")

    try:
        await close_pool()
        logger.info("Database pool closed")
    except Exception as e:
        logger.warning(f"Error closing database pool: {e}")


app = FastAPI(
    title="Session Dashboard",
    lifespan=lifespan,
)

# Include routers
app.include_router(health_router)
app.include_router(handoffs_router)
app.include_router(knowledge_router)
app.include_router(memory_router)
app.include_router(roadmap_router)

# Static files configuration
STATIC_DIR = Path(__file__).parent / "static"

# Mount assets directory for Vite build output (JS, CSS bundles)
# This must come AFTER API routes to not intercept API calls
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


@app.get("/")
async def root():
    """Serve the dashboard index page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"error": "Frontend not built. Run: cd frontend && npm run build"}


@app.get("/vite.svg")
async def serve_vite_svg():
    """Serve the Vite favicon."""
    svg_path = STATIC_DIR / "vite.svg"
    if svg_path.exists():
        return FileResponse(str(svg_path), media_type="image/svg+xml")
    return {"error": "vite.svg not found"}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """SPA fallback - serve index.html for all non-API routes.

    This enables client-side routing by serving the React app
    for any path that doesn't match an API route.
    """
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"error": "Frontend not built. Run: cd frontend && npm run build"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Handles subscription messages:
    - {"action": "subscribe", "project": "project-id"}
    - {"action": "unsubscribe", "project": "project-id"}

    Args:
        websocket: The WebSocket connection
    """
    import json

    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    project = message.get("project")
                    if not project:
                        await manager.send_personal(
                            client_id,
                            {"type": "error", "message": "Missing 'project' field"},
                        )
                        continue
                    await manager.subscribe(client_id, project)
                    await manager.send_personal(
                        client_id,
                        {
                            "type": "subscription",
                            "action": "subscribed",
                            "project": project,
                        },
                    )

                elif action == "unsubscribe":
                    project = message.get("project")
                    if not project:
                        await manager.send_personal(
                            client_id,
                            {"type": "error", "message": "Missing 'project' field"},
                        )
                        continue
                    await manager.unsubscribe(client_id, project)
                    await manager.send_personal(
                        client_id,
                        {
                            "type": "subscription",
                            "action": "unsubscribed",
                            "project": project,
                        },
                    )

                elif action is not None:
                    await manager.send_personal(
                        client_id,
                        {"type": "error", "message": f"Unknown action: {action}"},
                    )

            except json.JSONDecodeError:
                await manager.send_personal(
                    client_id,
                    {"type": "error", "message": "Invalid JSON message"},
                )
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


def run():
    """Run the uvicorn server with configured host and port."""
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
    )


if __name__ == "__main__":
    run()
