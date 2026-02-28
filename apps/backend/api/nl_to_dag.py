from __future__ import annotations

from fastapi import APIRouter
from models.schemas import NLToDAGRequest
from agents.nl_to_dag import NLToDAGAgent

router = APIRouter(tags=["nl-to-dag"])

agent = NLToDAGAgent()


@router.post("/api/agents/nl-to-dag/generate")
async def generate_dag(request: NLToDAGRequest):
    """Generate an Airflow DAG from a natural language description."""
    try:
        result = await agent.generate(request.description)
        return result
    except Exception as exc:
        return {"error": str(exc), "dag_code": "", "dag_id": "", "filename": ""}
