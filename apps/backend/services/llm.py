from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMService:
    """Wrapper around the Anthropic API for agent calls."""

    def __init__(self) -> None:
        self.client = None
        self.model = "claude-sonnet-4-20250514"
        try:
            from config.settings import get_settings
            settings = get_settings()
            if settings.ANTHROPIC_API_KEY:
                import anthropic
                self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.model = settings.MODEL
                logger.info("LLMService initialised with Anthropic API key.")
            else:
                logger.warning(
                    "ANTHROPIC_API_KEY not set. LLMService will return None "
                    "(agents will use sample data)."
                )
        except Exception as exc:
            logger.warning("Failed to initialise Anthropic client: %s", exc)

    async def call_agent(
        self,
        system_prompt: str,
        user_message: str,
        response_schema: Optional[dict] = None,
    ) -> Optional[dict]:
        """Call the Anthropic API and return parsed JSON.

        Returns ``None`` when the API key is missing or an error occurs so
        that callers can fall back to sample / mock data.
        """
        if self.client is None:
            return None

        try:
            schema_hint = ""
            if response_schema:
                schema_hint = (
                    "\n\nRespond with valid JSON matching this schema:\n"
                    + json.dumps(response_schema, indent=2)
                )

            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt + schema_hint,
                messages=[{"role": "user", "content": user_message}],
            )

            content = message.content[0].text

            # Try to extract JSON from the response
            # Handle cases where the model wraps JSON in markdown code blocks
            text = content.strip()
            if text.startswith("```"):
                # Remove markdown code fences
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)

            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON, returning None.")
            return None
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None


# Module-level singleton
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
