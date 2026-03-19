from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from agents.informatica_migration import InformaticaMigrationAgent
from agents.informatica_migration_advanced import InformaticaMigrationAdvancedAgent
from models.schemas import InformaticaMigrateRequest

router = APIRouter(tags=["informatica-migration"])
logger = logging.getLogger(__name__)

# Railway enforces a ~120s request timeout. We set our own timeout slightly
# below that so we can return a graceful error instead of a connection reset.
REQUEST_TIMEOUT = 100  # seconds

# ---------------------------------------------------------------------------
# In-memory job store for async advanced migrations
# ---------------------------------------------------------------------------
_jobs: dict[str, dict[str, Any]] = {}
_MAX_JOBS = 20  # keep memory bounded


def _evict_old_jobs():
    """Remove oldest completed jobs when store exceeds limit."""
    if len(_jobs) <= _MAX_JOBS:
        return
    completed = [
        (jid, j) for jid, j in _jobs.items() if j["status"] in ("done", "error")
    ]
    completed.sort(key=lambda x: x[1].get("updated", ""))
    while len(_jobs) > _MAX_JOBS and completed:
        jid, _ = completed.pop(0)
        del _jobs[jid]


# ---------------------------------------------------------------------------
# Standard migration (unchanged)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Advanced migration — async job + polling
# ---------------------------------------------------------------------------
@router.post("/api/agents/informatica-migration/migrate-advanced")
async def informatica_migrate_advanced(request: InformaticaMigrateRequest):
    """Start an advanced migration job and return a job ID immediately.

    The migration runs in the background. Use the GET endpoint to poll
    for progress and results. This avoids Railway's ~120s request timeout.
    """
    job_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    _jobs[job_id] = {
        "status": "running",
        "progress_message": "Starting migration...",
        "progress_current": 0,
        "progress_total": 0,
        "result": None,
        "error": None,
        "created": now,
        "updated": now,
    }
    _evict_old_jobs()

    async def on_progress(stage: str, message: str, current: int, total: int):
        _jobs[job_id]["progress_message"] = message
        _jobs[job_id]["progress_current"] = current
        _jobs[job_id]["progress_total"] = total
        _jobs[job_id]["updated"] = datetime.now(timezone.utc).isoformat()

    async def run_migration():
        try:
            agent = InformaticaMigrationAdvancedAgent()
            result = await agent.migrate(
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

            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = result
            _jobs[job_id]["updated"] = datetime.now(timezone.utc).isoformat()

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

        except Exception as exc:
            logger.exception("Advanced migration job %s failed", job_id)
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["updated"] = datetime.now(timezone.utc).isoformat()

    asyncio.create_task(run_migration())

    return {"job_id": job_id, "status": "running"}


@router.get("/api/agents/informatica-migration/migrate-advanced/{job_id}")
async def informatica_migrate_advanced_status(job_id: str):
    """Poll for the status of an advanced migration job.

    Returns progress while running, or the full result when done.
    Each request is short-lived so Railway's timeout is not an issue.
    """
    job = _jobs.get(job_id)
    if not job:
        return {"status": "not_found", "error": "Job not found"}

    if job["status"] == "running":
        return {
            "status": "running",
            "progress_message": job["progress_message"],
            "progress_current": job["progress_current"],
            "progress_total": job["progress_total"],
        }
    elif job["status"] == "done":
        result = job["result"]
        # Clean up job after delivering result to free memory
        del _jobs[job_id]
        return {"status": "done", "result": result}
    elif job["status"] == "error":
        error = job["error"]
        del _jobs[job_id]
        return {"status": "error", "error": error}

    return {"status": job["status"]}
