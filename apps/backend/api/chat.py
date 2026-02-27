from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.source_of_truth import SourceOfTruthAgent
from agents.data_triage import DataTriageAgent
from models.schemas import SearchRequest, ChatRequest

router = APIRouter(tags=["source-of-truth", "data-triage", "chat"])


# --- Original search endpoint (kept for backward compatibility) ---

@router.post("/api/agents/source-of-truth/search")
async def source_of_truth_search(request: SearchRequest):
    agent = SourceOfTruthAgent()
    result = await agent.search(request.query)

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Source of Truth",
        "message": f"Found recommended table for: \"{request.query}\"",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


# --- Chat endpoints ---

@router.post("/api/agents/source-of-truth/chat")
async def source_of_truth_chat(request: ChatRequest):
    agent = SourceOfTruthAgent()
    result = await agent.chat(request.message, request.history)

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Source of Truth",
        "message": f"Chat: \"{request.message[:60]}\"",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/data-triage/chat")
async def data_triage_chat(request: ChatRequest):
    agent = DataTriageAgent()
    result = await agent.chat(request.message, request.history)

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Data Triage",
        "message": f"Chat: \"{request.message[:60]}\"",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result
