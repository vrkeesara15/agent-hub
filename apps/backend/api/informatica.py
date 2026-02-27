from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.informatica_migration import InformaticaMigrationAgent
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
