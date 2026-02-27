from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# --- Source of Truth ---

class SearchRequest(BaseModel):
    query: str


class TableRecommendation(BaseModel):
    table_name: str
    project: str
    dataset: str
    why: list[str]
    stats: dict
    modernized: bool


class SearchResponse(BaseModel):
    recommended: TableRecommendation
    alternatives: list[dict]
    confidence: str


# --- Code Accelerator ---

class ConvertRequest(BaseModel):
    mode: str
    input_code: str
    source_format: Optional[str] = None


class ConvertResponse(BaseModel):
    output_code: str
    changes: list[str]
    warnings: list[str]
    completion_pct: int


# --- Data Triage ---

class ScanRequest(BaseModel):
    file_content: Optional[str] = None
    filename: Optional[str] = None
    git_url: Optional[str] = None


class TableHealth(BaseModel):
    name: str
    status: str
    issue: Optional[str] = None


class ScanIssue(BaseModel):
    table: str
    severity: str
    message: str
    actions: list[str]


class ScanResponse(BaseModel):
    filename: str
    tables_found: int
    tables: list[TableHealth]
    issues: list[ScanIssue]


class FixRequest(BaseModel):
    table: str
    original_code: str


class FixResponse(BaseModel):
    explanation: str
    original_line: str
    fixed_line: str
    additional_changes: list[str]


# --- Activity & Agents ---

class ActivityItem(BaseModel):
    id: str
    agent: str
    message: str
    timestamp: str


class AgentInfo(BaseModel):
    name: str
    slug: str
    description: str
    status: str
    stats: dict
