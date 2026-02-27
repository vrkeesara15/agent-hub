from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import yaml

from knowledge.loader import load_csv

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "knowledge_config.yaml")


class DataSource:
    """Represents a single data source file with its configuration."""

    def __init__(self, config: dict, data_dir: str) -> None:
        self.name: str = config["name"]
        self.file: str = config["file"]
        self.source_type: str = config["type"]
        self.priority: int = config.get("priority", 0)
        self.key_fields: list[str] = config.get("key_fields", [])
        self.description: str = config.get("description", "")
        self.data_dir: str = data_dir
        self.rows: list[dict] = []
        self.loaded_at: Optional[datetime] = None
        self.file_modified: Optional[float] = None

    @property
    def filepath(self) -> str:
        return os.path.join(self.data_dir, self.file)

    def load(self) -> bool:
        """Load or reload data from CSV file. Returns True if data changed."""
        filepath = self.filepath
        if not os.path.exists(filepath):
            logger.warning("Data file not found: %s", filepath)
            return False

        mtime = os.path.getmtime(filepath)
        if self.file_modified is not None and mtime == self.file_modified:
            return False  # File hasn't changed

        self.rows = load_csv(self.file, self.data_dir)
        self.loaded_at = datetime.now(timezone.utc)
        self.file_modified = mtime
        logger.info(
            "Loaded %d rows from %s (priority=%d)",
            len(self.rows), self.name, self.priority,
        )
        return True

    def has_changed(self) -> bool:
        """Check if the underlying file has been modified since last load."""
        filepath = self.filepath
        if not os.path.exists(filepath):
            return False
        mtime = os.path.getmtime(filepath)
        return self.file_modified is None or mtime != self.file_modified

    def find_by_name(self, query: str) -> list[dict]:
        """Find rows matching the query against key fields.
        Supports bidirectional substring matching so that both
        'fact_sales' matches 'analytics.fact_sales' and vice-versa."""
        query_lower = query.lower().strip()
        results = []
        for row in self.rows:
            for field in self.key_fields:
                value = str(row.get(field, "")).lower().strip()
                if value and (
                    query_lower == value
                    or query_lower in value
                    or value in query_lower
                ):
                    results.append(row)
                    break
        return results

    def search(self, query: str) -> list[dict]:
        """Full-text search across all fields in this source."""
        query_lower = query.lower().strip()
        results = []
        for row in self.rows:
            searchable = " ".join(str(v) for v in row.values()).lower()
            if query_lower in searchable:
                results.append(row)
        return results


class KnowledgeStore:
    """Enhanced knowledge store with prioritized multi-file lookup,
    configurable data sources, and automatic refresh."""

    def __init__(self) -> None:
        self._sources: list[DataSource] = []
        self._config: dict = {}
        self._last_refresh: Optional[float] = None
        self._refresh_interval: int = 86400  # Default 24 hours
        self._refresh_task: Optional[asyncio.Task] = None
        # Legacy compat
        self._data: dict[str, list[dict]] = {}

    def load_config(self) -> None:
        """Load the knowledge base configuration from YAML."""
        if not os.path.exists(CONFIG_PATH):
            logger.warning("Knowledge config not found at %s, using defaults", CONFIG_PATH)
            return

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

        self._refresh_interval = self._config.get("refresh_interval_seconds", 86400)
        data_dir_rel = self._config.get("data_directory", "data/sample")
        data_dir = os.path.join(BASE_DIR, data_dir_rel)

        self._sources = []
        for src_config in self._config.get("sources", []):
            source = DataSource(src_config, data_dir)
            self._sources.append(source)

        # Sort by priority descending (highest first)
        self._sources.sort(key=lambda s: s.priority, reverse=True)
        logger.info(
            "Loaded %d data source configs (priority order: %s)",
            len(self._sources),
            [s.name for s in self._sources],
        )

    def load_all_data(self) -> None:
        """Load all configured data sources."""
        loaded = 0
        total_rows = 0
        for source in self._sources:
            if source.load():
                loaded += 1
            total_rows += len(source.rows)
            # Also populate legacy _data dict for backward compat
            self._data[source.name] = source.rows

        self._last_refresh = time.time()
        logger.info(
            "Knowledge store loaded: %d sources, %d total rows",
            loaded, total_rows,
        )

    def load_sample_data(self) -> None:
        """Load all data — entry point called from main.py lifespan."""
        self.load_config()
        self.load_all_data()

    def refresh_if_needed(self) -> bool:
        """Check if any source files have changed and reload them.
        Returns True if any data was refreshed."""
        changed = False
        for source in self._sources:
            if source.has_changed():
                source.load()
                self._data[source.name] = source.rows
                changed = True
        if changed:
            self._last_refresh = time.time()
            logger.info("Knowledge store refreshed at %s", datetime.now(timezone.utc).isoformat())
        return changed

    async def start_auto_refresh(self) -> None:
        """Start a background task that periodically refreshes data."""
        if self._refresh_interval <= 0:
            logger.info("Auto-refresh disabled (interval=0)")
            return

        async def _refresh_loop():
            while True:
                await asyncio.sleep(self._refresh_interval)
                try:
                    self.refresh_if_needed()
                except Exception as exc:
                    logger.error("Auto-refresh failed: %s", exc)

        self._refresh_task = asyncio.create_task(_refresh_loop())
        logger.info("Auto-refresh started (interval=%ds)", self._refresh_interval)

    def stop_auto_refresh(self) -> None:
        """Stop the auto-refresh background task."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            logger.info("Auto-refresh stopped.")

    # ------------------------------------------------------------------
    # Lookup methods (prioritized across all sources)
    # ------------------------------------------------------------------

    @staticmethod
    def _name_variations(table_name: str) -> list[str]:
        """Generate search variations for a table name.
        e.g. 'analytics.fact_sales' -> ['analytics.fact_sales', 'fact_sales']
        e.g. 'vz-proj.dataset.table' -> ['vz-proj.dataset.table', 'dataset.table', 'table']
        """
        variations = [table_name]
        parts = table_name.replace("`", "").split(".")
        # Add progressively shorter suffixes
        for i in range(1, len(parts)):
            variation = ".".join(parts[i:])
            if variation and variation not in variations:
                variations.append(variation)
        return variations

    def lookup_table(self, table_name: str) -> dict:
        """Look up a table across all sources in priority order.
        Tries the full name first, then progressively shorter name variations
        (e.g. 'analytics.fact_sales' also tries 'fact_sales').
        Returns a merged result dict with data from all matching sources,
        plus metadata about which sources contributed."""
        merged: dict = {}
        source_hits: list[str] = []
        source_details: list[dict] = []
        matched_sources: set[str] = set()

        variations = self._name_variations(table_name)

        for source in self._sources:
            if source.name in matched_sources:
                continue
            # Try each name variation until one matches
            for variation in variations:
                matches = source.find_by_name(variation)
                if matches:
                    best = matches[0]
                    source_hits.append(source.name)
                    matched_sources.add(source.name)
                    source_details.append({
                        "source": source.name,
                        "type": source.source_type,
                        "priority": source.priority,
                        "data": best,
                    })
                    # Merge: higher priority sources' values take precedence
                    # Only fill in keys that aren't already set
                    for k, v in best.items():
                        if k not in merged and v and str(v).strip():
                            merged[k] = v
                    break  # Found match in this source, move to next

        return {
            "found": len(source_hits) > 0,
            "merged_data": merged,
            "sources": source_details,
            "source_names": source_hits,
        }

    def search_tables(self, query: str) -> list[dict]:
        """Search for tables across all sources. Returns deduplicated results
        with priority ordering."""
        query_lower = query.lower().strip()
        seen_tables: set[str] = set()
        results: list[dict] = []

        for source in self._sources:
            matches = source.search(query)
            for row in matches:
                # Build a table identifier from available fields
                table_id = (
                    row.get("gcp_table", "")
                    or row.get("table_name", "")
                    or row.get("legacy_table", "")
                    or row.get("target_table", "")
                ).lower()

                if table_id and table_id not in seen_tables:
                    seen_tables.add(table_id)
                    results.append({
                        **row,
                        "_source": source.name,
                        "_priority": source.priority,
                    })

        return results

    def get_table_info(self, table_name: str) -> Optional[dict]:
        """Get comprehensive info for a specific table by merging all sources."""
        lookup = self.lookup_table(table_name)
        if not lookup["found"]:
            return None

        merged = lookup["merged_data"]

        # Helper to check multiple possible field names (different CSVs use
        # different column names for the same concept).
        def _get(*keys: str, default: str = "") -> str:
            for k in keys:
                val = merged.get(k, "")
                if val and str(val).strip():
                    return str(val).strip()
            return default

        # Build a unified table info object
        info: dict = {
            "table_name": (
                _get("gcp_table", "table_name") or table_name
            ),
            "legacy_table": _get("legacy_table"),
            "legacy_database": _get("legacy_database"),
            "legacy_schema": _get("legacy_schema"),
            "object_type": _get("object_type", default="TABLE"),
            "gcp_project": _get("gcp_project", "project"),
            "gcp_dataset": _get("gcp_dataset", "dataset"),
            "gcp_table": _get("gcp_table"),
            "gcp_full_path": _get("gcp_full_path", "full_path"),
            "modernization_status": _get("modernization_status", "modernized"),
            "data_flipped": _get("data_flipped"),
            "flip_date": _get("flip_date"),
            "owner_team": _get("owner_team", "owner"),
            "refresh_cadence": _get("refresh_cadence", "schedule"),
            "row_count": _get("row_count"),
            "size_bytes": _get("size_bytes"),
            "num_columns": _get("num_columns"),
            "quality_score": _get("quality_score"),
            "created_date": _get("created_date"),
            "last_modified_date": _get("last_modified_date", "last_updated"),
            "last_queried_date": _get("last_queried_date"),
            "partitioned": _get("partitioned"),
            "partition_field": _get("partition_field"),
            "clustered": _get("clustered"),
            "cluster_fields": _get("cluster_fields"),
            "description": _get("description", "notes"),
            "labels": _get("labels"),
            "status": _get("status"),
            "health_status": _get("health_status"),
            "issue": _get("issue"),
            "sla_tier": _get("sla_tier"),
            "data_classification": _get("data_classification"),
            "deprecation_date": _get("deprecation_date"),
            "replacement_table": _get("replacement_table"),
            "migration_wave": _get("migration_wave"),
            "migration_status": _get("migration_status"),
            "sources_used": lookup["source_names"],
        }

        # Strip empty string values to keep it clean
        info = {k: v for k, v in info.items() if v != "" and v is not None}

        return info

    def get_all_table_names(self) -> list[str]:
        """Return a sorted list of all known table names from all sources."""
        names: set[str] = set()
        for source in self._sources:
            for row in source.rows:
                for field in ["gcp_table", "legacy_table", "table_name", "target_table"]:
                    val = row.get(field, "").strip()
                    if val:
                        names.add(val)
        return sorted(names)

    def get_tables_by_status(self, status: str) -> list[dict]:
        """Find tables with a specific status (active, deprecated, etc.)."""
        results = []
        for source in self._sources:
            if source.source_type in ("status", "mapping"):
                for row in source.rows:
                    row_status = (
                        row.get("status", "")
                        or row.get("health_status", "")
                        or row.get("modernization_status", "")
                    ).lower()
                    if status.lower() in row_status:
                        results.append(row)
        return results

    def get_tables_by_team(self, team: str) -> list[dict]:
        """Find tables owned by a specific team."""
        team_lower = team.lower()
        results = []
        for source in self._sources:
            for row in source.rows:
                owner = row.get("owner_team", "").lower()
                if team_lower in owner:
                    results.append(row)
        return results

    def get_dag_for_table(self, table_name: str) -> Optional[dict]:
        """Find the DAG/pipeline that feeds a specific table."""
        table_lower = table_name.lower()
        for source in self._sources:
            if source.source_type == "inventory":
                for row in source.rows:
                    target = row.get("target_table", "").lower()
                    if target and table_lower in target:
                        return row
        return None

    # ------------------------------------------------------------------
    # Legacy compatibility methods
    # ------------------------------------------------------------------

    def add_dataset(self, name: str, rows: list[dict]) -> None:
        """Add or replace a named dataset (for CSV upload)."""
        self._data[name] = rows
        # Also add as a dynamic DataSource
        existing = next((s for s in self._sources if s.name == name), None)
        if existing:
            existing.rows = rows
            existing.loaded_at = datetime.now(timezone.utc)
        else:
            source = DataSource(
                {"name": name, "file": "", "type": "custom", "priority": 60, "key_fields": []},
                "",
            )
            source.rows = rows
            source.loaded_at = datetime.now(timezone.utc)
            self._sources.append(source)
            self._sources.sort(key=lambda s: s.priority, reverse=True)

    def get_dataset(self, name: str) -> list[dict]:
        """Return a dataset by name, or empty list."""
        return self._data.get(name, [])

    @property
    def datasets(self) -> list[str]:
        """Return list of loaded dataset names."""
        return list(self._data.keys())

    def get_table_by_name(self, table_name: str) -> Optional[dict]:
        """Legacy method — find a table across all sources."""
        info = self.get_table_info(table_name)
        return info

    def get_table_health(self) -> list[dict]:
        """Return table health information."""
        for source in self._sources:
            if source.source_type == "status":
                return source.rows
        return self._data.get("table_mapping", [])

    def get_dag_inventory(self) -> list[dict]:
        """Return DAG inventory data."""
        for source in self._sources:
            if source.source_type == "inventory":
                return source.rows
        return self._data.get("dag_inventory", [])

    @property
    def source_info(self) -> list[dict]:
        """Return metadata about all loaded sources."""
        return [
            {
                "name": s.name,
                "type": s.source_type,
                "priority": s.priority,
                "rows": len(s.rows),
                "loaded_at": s.loaded_at.isoformat() if s.loaded_at else None,
                "description": s.description,
            }
            for s in self._sources
        ]


# Module-level singleton
_store: Optional[KnowledgeStore] = None


def get_knowledge_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
