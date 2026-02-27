from __future__ import annotations

from typing import Optional

from knowledge.store import get_knowledge_store


def get_table_metadata(table_name: str) -> Optional[dict]:
    """Return enriched metadata for a table by merging all knowledge sources."""
    store = get_knowledge_store()
    return store.get_table_info(table_name)


def get_all_table_names() -> list[str]:
    """Return a list of all known table names."""
    store = get_knowledge_store()
    return store.get_all_table_names()


def format_row_count(count_str: str) -> str:
    """Format a numeric row count string into a human-readable form."""
    try:
        count = int(count_str)
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.0f}K"
        return str(count)
    except (ValueError, TypeError):
        return count_str


def format_size(size_str: str) -> str:
    """Format a byte count string into a human-readable form."""
    try:
        size = int(size_str)
        if size >= 1_000_000_000:
            return f"{size / 1_000_000_000:.1f} GB"
        if size >= 1_000_000:
            return f"{size / 1_000_000:.1f} MB"
        if size >= 1_000:
            return f"{size / 1_000:.0f} KB"
        return f"{size} B"
    except (ValueError, TypeError):
        return size_str


def format_time_ago(iso_timestamp: str) -> str:
    """Convert an ISO timestamp to a human-readable 'X ago' string."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt

        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hrs ago"
        days = hours // 24
        if days < 30:
            return f"{days} days ago"
        months = days // 30
        return f"{months} months ago"
    except (ValueError, TypeError):
        return iso_timestamp or "unknown"
