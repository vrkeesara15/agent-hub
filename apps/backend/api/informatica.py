from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

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
    """Advanced migration using SSE streaming to keep the connection alive.

    Sends progress events while processing, then the final result as a
    JSON event. This prevents Railway/proxy timeouts on long-running
    LLM-powered migrations.
    """

    async def event_stream():
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def on_progress(stage: str, message: str, current: int, total: int):
            await progress_queue.put({
                "type": "progress",
                "stage": stage,
                "message": message,
                "current": current,
                "total": total,
            })

        async def run_migration():
            agent = InformaticaMigrationAdvancedAgent()
            return await agent.migrate(
                xml_content=request.xml_content,
                filename=request.filename,
                parameter_overrides=request.parameter_overrides,
                parameter_file_content=request.parameter_file_content,
                table_naming_config=request.table_naming_config,
                enable_reconciliation=request.enable_reconciliation,
                reconciliation_threshold_pct=request.reconciliation_threshold_pct,
                selected_mappings=request.selected_mappings,
                connection_config=request.connection_config,
                use_cache=request.use_cache,
                progress_callback=on_progress,
            )

        # Start migration in background task
        migration_task = asyncio.create_task(run_migration())

        # Stream progress events while migration runs, with keepalive
        while not migration_task.done():
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=15)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive comment to prevent proxy/Railway timeout
                yield ": keepalive\n\n"

        # Drain any remaining progress events
        while not progress_queue.empty():
            event = await progress_queue.get_nowait()
            yield f"data: {json.dumps(event)}\n\n"

        # Get final result
        try:
            result = await migration_task
        except Exception as exc:
            logger.exception("Advanced migration failed")
            error_event = {"type": "error", "error": str(exc)}
            yield f"data: {json.dumps(error_event)}\n\n"
            return

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

        # Send final result
        result_event = {"type": "result", "data": result}
        yield f"data: {json.dumps(result_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx/proxy buffering
        },
    )
