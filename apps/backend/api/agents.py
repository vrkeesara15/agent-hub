from __future__ import annotations

import os

import yaml
from fastapi import APIRouter

from models.schemas import AgentInfo

router = APIRouter(tags=["agents"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_YAML = os.path.join(BASE_DIR, "config", "agents.yaml")


def _load_agents() -> list[dict]:
    """Load agent definitions from the YAML config file."""
    try:
        with open(AGENTS_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("agents", [])
    except Exception:
        return []


@router.get("/api/agents")
async def list_agents() -> list[AgentInfo]:
    agents = _load_agents()
    return [
        AgentInfo(
            name=a["name"],
            slug=a["slug"],
            description=a["description"],
            status=a["status"],
            stats=a.get("stats", {}),
        )
        for a in agents
    ]


@router.get("/api/agents/{slug}")
async def get_agent(slug: str):
    agents = _load_agents()
    for a in agents:
        if a["slug"] == slug:
            return AgentInfo(
                name=a["name"],
                slug=a["slug"],
                description=a["description"],
                status=a["status"],
                stats=a.get("stats", {}),
            )
    return {"error": f"Agent '{slug}' not found"}
