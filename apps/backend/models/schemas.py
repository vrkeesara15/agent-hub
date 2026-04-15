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
    # --- Basic Info ---
    campaign_manager_name: str = ""
    message_code_type: str = "Message Code New"  # Message Code New | Message Code Existing | DAC
    message_positioning: str = "Proactive (Home/Mobile)"  # Proactive (Home/Mobile) | Reactive (Mobile) | DAC | CMID/SED (Mobile)
    refresh_frequency: str = "Daily"  # Adhoc | Daily | Monthly | Weekly | Dynamic Audience Code
    message_codes: str = ""  # the message code name(s)
    campaign_name: str = ""
    date_of_request: str = ""
    requested_due_date: str = ""

    # --- Product Info ---
    vz_service_type: str = ""
    product_family: str = ""
    offer_level: str = "Account"  # Account | Line
    product_description: str = ""
    product_owner: str = ""

    # --- Business Rules ---
    employees_included: str = "No"  # Yes | No
    dnsst_suppression: str = "YES"  # YES | No
    suppress_maine: str = "No"  # Yes | No
    maine_flag: str = ""  # Flag 1 BB | Flag 2 MB | Used in Customer Facing Channel
    feed_cards_live_tiles: str = "NO"  # Yes-AAL_P | Yes-LOYALTY_PROMO_P | Yes-PROMO_PRICING_P | Yes-REV GEN_P | Yes-RIGHT_PRICING_P | Yes-UPGRADE_P | Home Mixed | Yes-PROD_P | NO
    intended_purpose: str = ""  # Engagement | Revenue Generating | Stem Churn
    expected_kpi: str = ""
    target_criteria: str = ""
    suppressions: str = ""
    additional_info: str = ""

    # --- Holdout & Control ---
    holdout_group: str = "BOTH"  # CARHOG | PHOG | BOTH | CS_PHOG + PRS FIOS PHOG as OHOG | None
    control_pct: str = "0"

    # --- Compliance ---
    legal_approver: str = ""
    legally_approved: str = "Pending"  # Yes | No | Pending
    approval_date: str = ""
    viva_data: str = "No"  # Yes | No
    viva_jira_number: str = ""
    viva_privacy_legal_approved: str = "NA"  # Yes | No | Pending | NA
    cpni_data_used: str = "No"  # Yes | No
    cpni_usage_type: str = "Not Used"  # Not Used | Home Voice | Mobile
    ppi_data: str = "No"  # Yes | No
    ppi_usage_type: str = ""
    model_criteria_used: str = "No"  # Yes | No | NA

    # --- CDAE Internal ---
    mc_developer: str = ""
    dev_start_date: str = ""
    completion_date: str = ""
    validation_send_date: str = ""
    validation_due_date: str = ""
    production_date: str = ""
    log_check: str = "YES"  # YES | No
    new_message_codes: str = ""
    total_message_codes: str = ""
    scope: str = ""  # 1 | 2 | 3 | 4 | 5
    dbm_comments: str = ""
    mvp_prioritization: str = ""
    preliminary_counts: str = ""
    script_name: str = ""
    automation_folder: str = ""
    development_scope: str = ""

    # Legacy compat fields (used by template matching / generation)
    message_code: str = ""
    name: str = ""
    description: str = ""
    channel: str = "email"
    category: str = ""
    owner: str = ""
    schedule: str = "0 6 * * *"
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
