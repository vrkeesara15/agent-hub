from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from agents.message_code_builder import MessageCodeBuilderAgent, DEMO_PRESETS
from models.schemas import (
    MessageCodeGenerateRequest,
    MessageCodeRequirements,
    MessageCodeSaveRequest,
)

router = APIRouter(tags=["message-code-builder"])


@router.get("/api/agents/message-code-builder/templates")
async def list_templates():
    """List all available message code templates."""
    agent = MessageCodeBuilderAgent()
    return {"templates": agent.list_templates()}


@router.post("/api/agents/message-code-builder/analyze")
async def analyze_requirements(request: MessageCodeRequirements):
    """Analyze requirements and recommend the best template."""
    agent = MessageCodeBuilderAgent()
    result = await agent.analyze_requirements(request.model_dump())

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Message Code Builder",
        "message": f"Analyzed requirements for {request.message_code}: recommended template '{result.get('recommended_template', {}).get('name', 'N/A')}'",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/message-code-builder/generate")
async def generate_message_code(request: MessageCodeGenerateRequest):
    """Generate message code SQL from requirements and an optional template."""
    agent = MessageCodeBuilderAgent()
    result = await agent.generate_message_code(
        requirements=request.requirements.model_dump(),
        template_id=request.template_id,
    )

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Message Code Builder",
        "message": f"Generated message code: {request.requirements.message_code} (template: {result.get('template_name', 'auto')})",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/message-code-builder/dag")
async def generate_dag(request: MessageCodeRequirements):
    """Generate an Airflow DAG for a message code."""
    agent = MessageCodeBuilderAgent()
    result = agent.generate_dag(request.model_dump())

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Message Code Builder",
        "message": f"Generated DAG: {result.get('dag_id', 'unknown')} with schedule {result.get('cron', 'N/A')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.post("/api/agents/message-code-builder/erules")
async def generate_erules(request: MessageCodeRequirements):
    """Generate eRules output (General, Rule, CDP Select, eRule JSON) for the message code."""
    agent = MessageCodeBuilderAgent()
    result = agent.generate_erules(request.model_dump())

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Message Code Builder",
        "message": f"Generated eRules for target {result.get('target_id', 'unknown')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result


@router.get("/api/agents/message-code-builder/demo-presets")
async def get_demo_presets():
    """Return demo preset data for auto-populating the form during demos."""
    return {"presets": DEMO_PRESETS}


@router.post("/api/agents/message-code-builder/save")
async def save_to_knowledge(request: MessageCodeSaveRequest):
    """Save a message code to the knowledge base for future template matching."""
    agent = MessageCodeBuilderAgent()
    result = agent.save_to_knowledge(request.model_dump())

    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Message Code Builder",
        "message": f"Saved message code '{request.message_code}' to knowledge base (total: {result.get('total_templates', 0)} templates)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(activity_log) > 50:
        activity_log[:] = activity_log[-50:]

    return result
