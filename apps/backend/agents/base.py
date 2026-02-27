from __future__ import annotations

import logging
from typing import Optional

from services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents with common helper methods."""

    name: str = "BaseAgent"
    slug: str = "base"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self) -> None:
        self.llm: LLMService = get_llm_service()

    async def call_llm(
        self,
        user_message: str,
        response_schema: Optional[dict] = None,
    ) -> Optional[dict]:
        """Call the LLM with this agent's system prompt.

        Returns parsed JSON dict or None if the LLM is unavailable.
        """
        return await self.llm.call_agent(
            system_prompt=self.system_prompt,
            user_message=user_message,
            response_schema=response_schema,
        )

    def get_sample_response(self) -> dict:
        """Override in subclasses to provide fallback sample data."""
        return {}
