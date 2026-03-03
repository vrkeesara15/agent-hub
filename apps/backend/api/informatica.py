from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.informatica_migration import InformaticaMigrationAgent
from agents.informatica_migration_advanced import InformaticaMigrationAdvancedAgent
from models.schemas import InformaticaMigrateRequest

router = APIRouter(tags=["informatica-migration"])


@router.post("/api/agents/informatica-migration/migrate")
async def informatica_migrate(request: InformaticaMigrateRequest):
    agent = InformaticaMigrationAgent()
    result = await agent.migrate(
        xml_content=request.xml_content,
        filename=request.filename,
    )

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
    result = await agent.migrate(
        xml_content=request.xml_content,
        filename=request.filename,
    )

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
