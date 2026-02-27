from __future__ import annotations

import os
from pydantic_settings import BaseSettings


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
