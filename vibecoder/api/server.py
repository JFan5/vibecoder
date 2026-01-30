"""FastAPI application for VibeCoder."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from ..config import config
from ..core.engine import get_engine


# Get the directory containing static files
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    engine = get_engine()

    # Start engine in background
    engine_task = asyncio.create_task(engine.start())

    yield

    # Stop engine on shutdown
    engine.stop()
    engine_task.cancel()
    try:
        await engine_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="VibeCoder",
    description="Autonomous AI Coding Orchestration System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from .routes import tasks, approvals, logs

app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])

# Import websocket handler
from .websocket import websocket_endpoint

app.add_api_websocket_route("/ws", websocket_endpoint)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the dashboard."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return """
    <html>
        <head><title>VibeCoder</title></head>
        <body>
            <h1>VibeCoder</h1>
            <p>API is running. Dashboard files not found.</p>
            <p>API documentation: <a href="/docs">/docs</a></p>
        </body>
    </html>
    """


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/status")
async def get_status():
    """Get system status."""
    engine = get_engine()
    stats = engine.get_status()

    return {
        "status": stats.status.value,
        "pending_count": stats.pending_count,
        "running_count": stats.running_count,
        "completed_count": stats.completed_count,
        "failed_count": stats.failed_count,
        "total_processed": stats.total_processed,
        "start_time": stats.start_time.isoformat() if stats.start_time else None,
    }


@app.post("/api/queue/pause")
async def pause_queue():
    """Pause queue processing."""
    engine = get_engine()
    engine.pause()
    return {"status": "paused"}


@app.post("/api/queue/resume")
async def resume_queue():
    """Resume queue processing."""
    engine = get_engine()
    engine.resume()
    return {"status": "running"}
