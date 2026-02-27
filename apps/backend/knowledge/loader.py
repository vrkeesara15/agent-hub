from __future__ import annotations

import csv
import io
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample")


def load_csv(filename: str, directory: Optional[str] = None) -> list[dict]:
    """Load a CSV file and return rows as a list of dicts."""
    dir_path = directory or SAMPLE_DIR
    filepath = os.path.join(dir_path, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [dict(row) for row in reader]
        logger.info("Loaded %d rows from %s", len(rows), filepath)
        return rows
    except FileNotFoundError:
        logger.warning("CSV file not found: %s", filepath)
        return []
    except Exception as exc:
        logger.warning("Error loading CSV %s: %s", filepath, exc)
        return []


def load_csv_from_content(content: str) -> list[dict]:
    """Parse CSV content string and return rows as a list of dicts."""
    try:
        reader = csv.DictReader(io.StringIO(content))
        return [dict(row) for row in reader]
    except Exception as exc:
        logger.warning("Error parsing CSV content: %s", exc)
        return []


def load_all_sample_data() -> dict[str, list[dict]]:
    """Load all CSV files from the sample data directory."""
    data: dict[str, list[dict]] = {}
    if not os.path.isdir(SAMPLE_DIR):
        logger.warning("Sample directory not found: %s", SAMPLE_DIR)
        return data

    for filename in os.listdir(SAMPLE_DIR):
        if filename.endswith(".csv"):
            key = filename.replace(".csv", "")
            data[key] = load_csv(filename)
    return data
