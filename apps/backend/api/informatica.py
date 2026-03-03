from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.informatica_migration import InformaticaMigrationAgent
from agents.informatica_migration_advanced import InformaticaMigrationAdvancedAgent
from models.schemas import InformaticaMigrateRequest

router = APIRouter(tags=["informatica-migration"])
logger = logging.getLogger(__name__)

# Railway enforces a ~120s request timeout. We set our own timeout slightly
# below that so we can return a graceful error instead of a connection reset.
REQUEST_TIMEOUT = 100  # seconds


@router.post("/api/agents/informatica-migration/migrate")
async def informatica_migrate(request: InformaticaMigrateRequest):
    agent = InformaticaMigrationAgent()
    try:
        result = await asyncio.wait_for(
            agent.migrate(
                xml_content=request.xml_content,
                filename=request.filename,
            ),
            timeout=REQUEST_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Standard migration timed out for %s", request.filename)
        return {"error": "Migration timed out. The workflow may be too large. Try Advanced mode for complex workflows."}

    # Record activity
    from main import activity_log
    wf_name = result.get("workflow_name", request.filename)
    complexity = result.get("complexity", "unknown")
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Informatica Migration",
        "message": f"Migrated '{wf_name}' (complexity: {complexity})",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/informatica-migration/migrate-advanced")
async def informatica_migrate_advanced(request: InformaticaMigrateRequest):
    agent = InformaticaMigrationAdvancedAgent()
    try:
        result = await asyncio.wait_for(
            agent.migrate(
                xml_content=request.xml_content,
                filename=request.filename,
            ),
            timeout=REQUEST_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Advanced migration timed out for %s", request.filename)
        return {"error": "Migration timed out. The workflow is very large — try splitting it into smaller XML files."}

    # Record activity
    from main import activity_log
    wf_name = result.get("workflow_name", request.filename)
    complexity = result.get("complexity", "unknown")
    score = result.get("scorecard", {}).get("overall_score", "N/A")
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Informatica Migration (Advanced)",
        "message": f"Migrated '{wf_name}' (complexity: {complexity}, score: {score}%)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result
