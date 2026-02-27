from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.code_accelerator import CodeAcceleratorAgent
from agents.data_triage import DataTriageAgent
from models.schemas import ConvertRequest, FixRequest, ScanRequest

router = APIRouter(tags=["data-triage", "code-accelerator"])


@router.post("/api/agents/data-triage/scan")
async def data_triage_scan(request: ScanRequest):
    agent = DataTriageAgent()
    result = await agent.scan(
        file_content=request.file_content,
        filename=request.filename,
    )

    # Record activity
    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Data Triage",
        "message": f"Scanned {request.filename or 'file'}: found {result.get('tables_found', 0)} tables, {len(result.get('issues', []))} issues",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/data-triage/fix")
async def data_triage_fix(request: FixRequest):
    agent = DataTriageAgent()
    result = await agent.fix(
        table=request.table,
        original_code=request.original_code,
    )

    # Record activity
    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Data Triage",
        "message": f"Generated fix for table: {request.table}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/code-accelerator/convert")
async def code_accelerator_convert(request: ConvertRequest):
    agent = CodeAcceleratorAgent()
    result = await agent.convert(
        mode=request.mode,
        input_code=request.input_code,
        source_format=request.source_format,
    )

    # Record activity
    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Code Accelerator",
        "message": f"Converted code ({request.mode}): {request.source_format or 'auto-detect'} migration",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result
