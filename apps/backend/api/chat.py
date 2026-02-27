from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.source_of_truth import SourceOfTruthAgent
from models.schemas import SearchRequest, SearchResponse

router = APIRouter(tags=["source-of-truth"])


@router.post("/api/agents/source-of-truth/search")
async def source_of_truth_search(request: SearchRequest):
    agent = SourceOfTruthAgent()
    result = await agent.search(request.query)

    # Record activity
    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Source of Truth",
        "message": f"Found recommended table for: \"{request.query}\"",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep only the last 50 items
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result
