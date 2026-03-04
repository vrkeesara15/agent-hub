from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env FIRST with override=True so .env values always win
# over stale/empty shell exports.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    ANTHROPIC_API_KEY: str = ""
    API_URL: str = "https://api.anthropic.com"
    MODEL: str = "claude-sonnet-4-20250514"
    APP_NAME: str = "Agent Hub Backend"
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
