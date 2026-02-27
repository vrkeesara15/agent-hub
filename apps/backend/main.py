from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure the backend directory is on sys.path so that all local packages
# can be imported regardless of how the app is launched.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load .env file if present
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from knowledge.store import get_knowledge_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global in-memory activity log
# ---------------------------------------------------------------------------
activity_log: list[dict] = [
    {
        "id": "welcome-001",
        "agent": "user",
        "message": "Welcome to Agent Hub! Use an agent to see activity here.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
]

# Track read notification IDs
read_notifications: set[str] = set()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load knowledge base data on startup and start auto-refresh."""
    logger.info("Loading knowledge base into KnowledgeStore...")
    store = get_knowledge_store()
    store.load_sample_data()
    logger.info("Datasets loaded: %s", store.datasets)
    logger.info("Data sources: %s", [s["name"] for s in store.source_info])

    # Start auto-refresh for daily knowledge base updates
    await store.start_auto_refresh()

    yield

    store.stop_auto_refresh()
    logger.info("Shutting down Agent Hub backend.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Agent Hub Backend",
    description="Backend API for the Agent Hub multi-agent data platform.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
from api.health import router as health_router
from api.agents import router as agents_router
from api.chat import router as chat_router
from api.knowledge import router as knowledge_router
from api.triage import router as triage_router

app.include_router(health_router)
app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(triage_router)


# ---------------------------------------------------------------------------
# Activity endpoint (lives in main because it uses the global activity_log)
# ---------------------------------------------------------------------------
@app.get("/api/activity", tags=["activity"])
async def get_activity():
    """Return the last 10 activity items, newest first."""
    return activity_log[-10:][::-1]


# ---------------------------------------------------------------------------
# Notifications (derived from activity log with read tracking)
# ---------------------------------------------------------------------------
@app.get("/api/notifications", tags=["notifications"])
async def get_notifications():
    """Return activity items as notifications with read status."""
    items = activity_log[-20:][::-1]
    return [
        {
            **item,
            "read": item["id"] in read_notifications,
        }
        for item in items
    ]


@app.post("/api/notifications/{notification_id}/read", tags=["notifications"])
async def mark_notification_read(notification_id: str):
    """Mark a single notification as read."""
    read_notifications.add(notification_id)
    return {"success": True}


@app.post("/api/notifications/read-all", tags=["notifications"])
async def mark_all_notifications_read():
    """Mark all current notifications as read."""
    for item in activity_log:
        read_notifications.add(item["id"])
    return {"success": True}


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/", tags=["root"])
async def root():
    return {
        "name": "Agent Hub Backend",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
