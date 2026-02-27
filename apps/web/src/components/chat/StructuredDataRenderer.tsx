'use client';
import React from 'react';
import { ConfidenceBadge } from '@/components/source-of-truth/ConfidenceBadge';

// Helper to safely get string from unknown
function s(val: unknown): string {
  if (val === null || val === undefined) return '';
  return String(val);
}

// Helper to safely get number
function n(val: unknown): number {
  if (val === null || val === undefined) return 0;
  const num = Number(val);
  return isNaN(num) ? 0 : num;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyRecord = Record<string, any>;

/* ------- Table Recommendation Renderer ------- */
function TableRecommendationCard({ data }: { data: AnyRecord }) {
  const rec = data.recommended as AnyRecord | undefined;
  const alternatives = data.alternatives as AnyRecord[] | undefined;
  const confidence = s(data.confidence);

  if (!rec) return null;

  const stats = rec.stats as AnyRecord | undefined;
  const whyList = rec.why as string[] | undefined;

  return (
    <div className="space-y-3">
      {/* Main recommendation */}
      <div className="bg-green-50 dark:bg-green-950/30 border-l-4 border-status-success rounded-button p-4">
        <div className="flex items-center gap-2 mb-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" fill="#22C55E" />
            <path d="M8 12l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-xs font-bold uppercase tracking-wider text-status-success">Recommended Table</span>
        </div>
        <p className="text-lg font-bold text-brand-blue mb-2">{s(rec.table_name)}</p>

        {/* GCP details */}
        {(s(rec.project) || s(rec.dataset)) ? (
          <div className="flex flex-wrap gap-3 mb-3 text-xs text-text-secondary">
            {s(rec.project) ? <span>Project: <strong className="text-text-primary">{s(rec.project)}</strong></span> : null}
            {s(rec.dataset) ? <span>Dataset: <strong className="text-text-primary">{s(rec.dataset)}</strong></span> : null}
          </div>
        ) : null}

        {/* Why */}
        {whyList && whyList.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-bold text-text-primary mb-1">Why This Table:</p>
            <ul className="list-disc list-inside text-xs text-text-secondary space-y-0.5">
              {whyList.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div className="flex flex-wrap gap-4 text-xs">
            {s(stats.row_count) ? (
              <span className="text-text-secondary">
                Rows: <strong className="text-text-primary">{s(stats.row_count)}</strong>
              </span>
            ) : null}
            {s(stats.last_updated) ? (
              <span className="text-text-secondary">
                Updated: <strong className="text-text-primary">{s(stats.last_updated)}</strong>
              </span>
            ) : null}
            {n(stats.quality_score) > 0 ? (
              <span className="text-text-secondary">
                Quality: <strong className="text-text-primary">{s(stats.quality_score)}/100</strong>
              </span>
            ) : null}
          </div>
        )}
      </div>

      {/* Alternatives */}
      {alternatives && alternatives.length > 0 && (
        <div className="bg-surface-bg rounded-button p-3">
          <p className="text-xs font-bold text-text-primary mb-2">Other Tables:</p>
          <div className="space-y-1">
            {alternatives.map((alt, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full ${
                  s(alt.status) === 'deprecated' ? 'bg-status-danger' : 'bg-status-warning'
                }`} />
                <span className="font-medium text-text-primary">{s(alt.table_name)}</span>
                <span className="text-text-muted">- {s(alt.reason)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Confidence */}
      {confidence && (
        <div className="flex justify-end">
          <ConfidenceBadge level={confidence as 'high' | 'medium' | 'low'} />
        </div>
      )}
    </div>
  );
}

/* ------- Health Check Renderer ------- */
function HealthCheckCard({ data }: { data: AnyRecord }) {
  const tables = data.tables as AnyRecord[] | undefined;
  const issues = data.issues as AnyRecord[] | undefined;
  const tablesFound = data.tables_found as number | undefined;

  return (
    <div className="space-y-3">
      {/* Summary */}
      {tablesFound !== undefined && (
        <div className="bg-surface-bg rounded-button p-3">
          <p className="text-xs font-bold text-text-primary">
            Tables Found: <span className="text-brand-blue">{tablesFound}</span>
          </p>
        </div>
      )}

      {/* Tables */}
      {tables && tables.length > 0 && (
        <div className="bg-surface-bg rounded-button p-3">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-text-muted">
                <th className="pb-1">Table</th>
                <th className="pb-1">Status</th>
                <th className="pb-1">Issue</th>
              </tr>
            </thead>
            <tbody>
              {tables.map((t, i) => (
                <tr key={i} className="border-t border-surface-border">
                  <td className="py-1.5 font-mono text-text-primary">{s(t.name)}</td>
                  <td className="py-1.5">
                    <span className={`inline-flex items-center gap-1 ${
                      s(t.status) === 'healthy' ? 'text-status-success' :
                      s(t.status) === 'warning' ? 'text-status-warning' : 'text-status-danger'
                    }`}>
                      {s(t.status) === 'healthy' ? '✅' : s(t.status) === 'warning' ? '⚠️' : '🔴'}
                      {s(t.status)}
                    </span>
                  </td>
                  <td className="py-1.5 text-text-muted">{s(t.issue) || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Issues */}
      {issues && issues.length > 0 && (
        <div className="bg-red-50 dark:bg-red-950/30 border-l-4 border-status-danger rounded-button p-3">
          <p className="text-xs font-bold text-status-danger mb-2">
            {issues.length} Issue{issues.length > 1 ? 's' : ''} Found
          </p>
          <div className="space-y-2">
            {issues.map((issue, i) => (
              <div key={i} className="text-xs">
                <span className={`font-medium ${
                  s(issue.severity) === 'critical' ? 'text-status-danger' : 'text-status-warning'
                }`}>
                  [{s(issue.severity || 'warning').toUpperCase()}]
                </span>{' '}
                <span className="text-text-primary">{s(issue.message)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------- Main Renderer ------- */
export function renderStructuredData(data: Record<string, unknown>, dataType: string): React.ReactNode {
  switch (dataType) {
    case 'table_recommendation':
      return <TableRecommendationCard data={data} />;
    case 'health_check':
      return <HealthCheckCard data={data} />;
    default:
      return (
        <pre className="text-xs bg-surface-bg p-2 rounded-button overflow-x-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
}
