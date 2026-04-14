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


# --- Chat ---

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    response_text: str
    structured_data: Optional[dict] = None
    data_type: Optional[str] = None


# --- SQL Optimizer ---

class OptimizeRequest(BaseModel):
    input_code: str


class OptimizeResponse(BaseModel):
    health_score: int
    critical_issues: list[dict]
    warnings: list[dict]
    recommendations: list[str]
    optimized_code: str


# --- Informatica Migration ---

class InformaticaMigrateRequest(BaseModel):
    xml_content: str  # str or list[str] for multi-XML
    filename: str = "workflow.xml"
    parameter_overrides: Optional[dict[str, str]] = None
    parameter_file_content: Optional[str] = None
    table_naming_config: Optional[dict] = None
    enable_reconciliation: bool = True
    reconciliation_threshold_pct: float = 5.0
    selected_mappings: Optional[list[str]] = None
    connection_config: Optional[dict] = None
    use_cache: bool = True


# --- NL to DAG ---

class NLToDAGRequest(BaseModel):
    description: str


# --- Message Code Builder ---

class MessageCodeRequirements(BaseModel):
    message_code: str = "MC_NEW_MESSAGE"
    name: str = "New Message"
    description: str = ""
    channel: str = "email"
    category: str = ""
    owner: str = "team"
    schedule: str = "Daily 08:00 UTC"
    audience_rules: str = ""
    exclusion_rules: str = ""
    extra_fields: str = ""


class MessageCodeGenerateRequest(BaseModel):
    requirements: MessageCodeRequirements
    template_id: Optional[str] = None


class MessageCodeSaveRequest(BaseModel):
    message_code: str
    name: str
    description: str = ""
    channel: str = "email"
    category: str = ""
    owner: str = ""
    schedule: str = ""
    sql: str = ""
    logic_summary: str = ""
    tags: list[str] = []
