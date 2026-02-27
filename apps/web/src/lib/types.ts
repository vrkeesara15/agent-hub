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
