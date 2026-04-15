export interface TableRecommendation {
  table_name: string;
  project: string;
  dataset: string;
  why: string[];
  stats: {
    row_count: string;
    last_updated: string;
    quality_score: number;
  };
  modernized: boolean;
}

export interface TableAlternative {
  table_name: string;
  status: 'warning' | 'deprecated' | 'stale';
  reason: string;
}

export interface SearchResponse {
  recommended: TableRecommendation;
  alternatives: TableAlternative[];
  confidence: 'high' | 'medium' | 'low';
}

export interface ConversionChange {
  original: string;
  converted: string;
  explanation: string;
}

export interface ConversionWarning {
  type: string;
  message: string;
}

export interface ConvertResponse {
  output_code: string;
  changes: ConversionChange[];
  warnings: ConversionWarning[];
  completion_pct: number;
}

export interface TableHealth {
  name: string;
  status: 'healthy' | 'warning' | 'alert';
  issue: string | null;
}

export interface ScanIssue {
  table: string;
  severity: 'critical' | 'warning';
  message: string;
  actions: string[];
}

export interface ScanResponse {
  filename: string;
  tables_found: number;
  tables: TableHealth[];
  issues: ScanIssue[];
}

export interface FixResponse {
  explanation: string;
  original_line: string;
  fixed_line: string;
  additional_changes: string[];
}

export interface ActivityItem {
  id: string;
  agent: string;
  message: string;
  timestamp: string;
}

export interface AgentInfo {
  name: string;
  slug: string;
  description: string;
  status: string;
  stats: Record<string, string | number>;
}

export interface NotificationItem {
  id: string;
  agent: string;
  message: string;
  timestamp: string;
  read: boolean;
}

// --- Chat ---

export interface ChatMessageType {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  response_text: string;
  structured_data?: Record<string, unknown> | null;
  data_type?: string | null;
}

// --- SQL Optimizer ---

export interface OptimizeIssue {
  title: string;
  description: string;
  suggestion: string;
}

export interface OptimizeResponse {
  health_score: number;
  critical_issues: OptimizeIssue[];
  warnings: OptimizeIssue[];
  recommendations: string[];
  optimized_code: string;
}

// --- Informatica Migration ---

export interface TransformationMapItem {
  informatica: string;
  gcp: string;
  type: string;
  sql?: string;
}

export interface UnsupportedPattern {
  pattern: string;
  suggestion: string;
}

export interface InformaticaMigrationResponse {
  bigquery_sql: string;
  airflow_dag: string;
  transformation_map: TransformationMapItem[];
  unsupported_patterns: UnsupportedPattern[];
  scd_merge: string;
  summary: string;
  complexity: string;
  recommendations: string[];
  sources: string[];
  targets: string[];
  workflow_name: string;
  analysis: {
    total_transformations: number;
    sql_convertible: number;
    needs_dataflow: number;
    has_scd_pattern: boolean;
    complexity: string;
  };
  error?: string;
}

// --- Informatica Migration Advanced ---

export interface MigrationScorecard {
  overall_score: number;
  sql_coverage: number;
  target_coverage: number;
  expression_fidelity: number;
  dag_completeness: number;
  parameter_resolution: number;
  scd_coverage: number;
}

export interface MappingResult {
  mapping_name: string;
  status: 'converted' | 'partial' | 'failed';
  sql: string;
  transformations_used: number;
  transformations_converted: number;
  expressions_converted: number;
  expressions_total: number;
  issues: string[];
  used_llm: boolean;
}

export interface ExtractedParameter {
  name: string;
  default_value: string;
  used_in_mappings: string[];
  type_guess: string;
}

export interface ExpressionComparison {
  original: string;
  converted: string;
  status: 'converted' | 'partial' | 'failed';
  mapping: string;
}

export interface InformaticaAdvancedMigrationResponse extends InformaticaMigrationResponse {
  scorecard: MigrationScorecard;
  mapping_results: MappingResult[];
  parameters: ExtractedParameter[];
  expression_comparisons: ExpressionComparison[];
  mapping_sql_files?: Record<string, string>;
}

// --- NL to DAG ---

export interface NLToDAGResponse {
  dag_code: string;
  dag_id: string;
  description: string;
  used_llm: boolean;
  filename: string;
  error?: string;
}

// --- Message Code Builder ---

export interface MessageCodeRequirements {
  // Basic Info
  campaign_manager_name: string;
  message_code_type: string;
  message_positioning: string;
  refresh_frequency: string;
  message_codes: string;
  campaign_name: string;
  date_of_request: string;
  requested_due_date: string;

  // Product Info
  vz_service_type: string;
  product_family: string;
  offer_level: string;
  product_description: string;
  product_owner: string;

  // Business Rules
  employees_included: string;
  dnsst_suppression: string;
  suppress_maine: string;
  maine_flag: string;
  feed_cards_live_tiles: string;
  intended_purpose: string;
  expected_kpi: string;
  target_criteria: string;
  suppressions: string;
  additional_info: string;

  // Holdout & Control
  holdout_group: string;
  control_pct: string;

  // Compliance
  legal_approver: string;
  legally_approved: string;
  approval_date: string;
  viva_data: string;
  viva_jira_number: string;
  viva_privacy_legal_approved: string;
  cpni_data_used: string;
  cpni_usage_type: string;
  ppi_data: string;
  ppi_usage_type: string;
  model_criteria_used: string;

  // CDAE Internal
  mc_developer: string;
  dev_start_date: string;
  completion_date: string;
  validation_send_date: string;
  validation_due_date: string;
  production_date: string;
  log_check: string;
  new_message_codes: string;
  total_message_codes: string;
  scope: string;
  dbm_comments: string;
  mvp_prioritization: string;
  preliminary_counts: string;
  script_name: string;
  automation_folder: string;
  development_scope: string;

  // Legacy compat (used by template engine)
  message_code: string;
  name: string;
  description: string;
  channel: string;
  category: string;
  owner: string;
  schedule: string;
  audience_rules: string;
  exclusion_rules: string;
  extra_fields: string;
}

export interface MessageCodeTemplate {
  id: string;
  name: string;
  category: string;
  channel: string;
  description: string;
  tags: string[];
  logic_summary?: string;
  sql?: string;
}

export interface MessageCodeAnalyzeResponse {
  recommended_template: MessageCodeTemplate;
  alternatives: {
    id: string;
    name: string;
    category: string;
    channel: string;
    description: string;
    relevance: string;
  }[];
  match_reasoning: string;
}

export interface MessageCodeChange {
  section: string;
  description: string;
}

export interface MessageCodeGenerateResponse {
  sql: string;
  changes: MessageCodeChange[];
  logic_summary: string;
  warnings: string[];
  template_used: string;
  template_name: string;
}

export interface MessageCodeDAGResponse {
  dag_code: string;
  dag_id: string;
  cron: string;
  filename: string;
}

export interface MessageCodeSaveResponse {
  saved: boolean;
  id: string;
  total_templates: number;
}
