from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File

from knowledge.loader import load_csv_from_content
from knowledge.store import get_knowledge_store

router = APIRouter(tags=["knowledge"])


@router.post("/api/knowledge/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file to the knowledge store."""
    content = await file.read()
    text = content.decode("utf-8")

    rows = load_csv_from_content(text)
    if not rows:
        return {"error": "Could not parse CSV file", "rows_loaded": 0}

    # Use filename without extension as dataset name
    name = file.filename or "uploaded"
    if name.endswith(".csv"):
        name = name[:-4]

    store = get_knowledge_store()
    store.add_dataset(name, rows)

    # Record activity
    from main import activity_log
    activity_log.append({
        "id": str(uuid.uuid4())[:8],
        "agent": "Knowledge Store",
        "message": f"Uploaded {name}.csv with {len(rows)} rows",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "filename": file.filename,
        "dataset_name": name,
        "rows_loaded": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
    }


@router.get("/api/knowledge/datasets")
async def list_datasets():
    """List all loaded datasets."""
    store = get_knowledge_store()
    datasets = []
    for name in store.datasets:
        data = store.get_dataset(name)
        datasets.append({
            "name": name,
            "rows": len(data),
            "columns": list(data[0].keys()) if data else [],
        })
    return {"datasets": datasets}


@router.get("/api/knowledge/sources")
async def list_sources():
    """List all configured data sources with their priority and status."""
    store = get_knowledge_store()
    return {
        "sources": store.source_info,
        "total_tables": len(store.get_all_table_names()),
    }


@router.post("/api/knowledge/refresh")
async def refresh_knowledge():
    """Trigger a manual refresh of the knowledge base.
    Reloads any CSV files that have changed on disk."""
    store = get_knowledge_store()
    changed = store.refresh_if_needed()

    from main import activity_log
    if changed:
        activity_log.append({
            "id": str(uuid.uuid4())[:8],
            "agent": "Knowledge Store",
            "message": "Knowledge base refreshed with updated data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "refreshed": changed,
        "sources": store.source_info,
        "total_tables": len(store.get_all_table_names()),
    }


@router.get("/api/knowledge/tables")
async def list_tables():
    """List all known table names from all sources."""
    store = get_knowledge_store()
    return {"tables": store.get_all_table_names()}


@router.get("/api/knowledge/table/{table_name}")
async def get_table_info(table_name: str):
    """Get comprehensive information for a specific table."""
    store = get_knowledge_store()
    info = store.get_table_info(table_name)
    if not info:
        return {"found": False, "table_name": table_name, "message": "Table not found in knowledge base"}
    return {"found": True, **info}
