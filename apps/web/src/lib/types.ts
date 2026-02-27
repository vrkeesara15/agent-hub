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
