'use client';
import React from 'react';
import { OptimizeResponse } from '@/lib/types';

interface SQLAnalysisProps {
  result: OptimizeResponse;
}

export function SQLAnalysis({ result }: SQLAnalysisProps) {
  const scoreColor =
    result.health_score >= 80 ? 'text-status-success' :
    result.health_score >= 50 ? 'text-status-warning' : 'text-status-danger';

  const scoreBg =
    result.health_score >= 80 ? 'bg-green-50 dark:bg-green-950/30 border-status-success' :
    result.health_score >= 50 ? 'bg-amber-50 dark:bg-amber-950/30 border-status-warning' :
    'bg-red-50 dark:bg-red-950/30 border-status-danger';

  return (
    <div className="space-y-4">
      {/* Health Score */}
      <div className={`${scoreBg} border-l-4 rounded-card p-5`}>
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className={`text-4xl font-bold ${scoreColor}`}>{result.health_score}</div>
            <div className="text-xs text-text-muted uppercase tracking-wide mt-1">Health Score</div>
          </div>
          <div className="flex-1">
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
              <div
                className={`h-3 rounded-full transition-all ${
                  result.health_score >= 80 ? 'bg-status-success' :
                  result.health_score >= 50 ? 'bg-status-warning' : 'bg-status-danger'
                }`}
                style={{ width: `${result.health_score}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Critical Issues */}
      {result.critical_issues.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-status-danger flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-status-danger" />
            Critical Issues ({result.critical_issues.length})
          </h3>
          <div className="space-y-2">
            {result.critical_issues.map((issue, i) => (
              <div key={i} className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-card p-4">
                <p className="text-sm font-bold text-text-primary mb-1">{issue.title}</p>
                <p className="text-xs text-text-secondary mb-2">{issue.description}</p>
                <div className="text-xs text-status-success bg-green-50 dark:bg-green-950/30 rounded-button px-3 py-1.5 inline-block">
                  Fix: {issue.suggestion}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-status-warning flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-status-warning" />
            Warnings ({result.warnings.length})
          </h3>
          <div className="space-y-2">
            {result.warnings.map((warning, i) => (
              <div key={i} className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-card p-4">
                <p className="text-sm font-bold text-text-primary mb-1">{warning.title}</p>
                <p className="text-xs text-text-secondary mb-2">{warning.description}</p>
                <div className="text-xs text-brand-blue bg-blue-50 dark:bg-blue-950/30 rounded-button px-3 py-1.5 inline-block">
                  Suggestion: {warning.suggestion}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {result.recommendations.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-text-primary flex items-center gap-2 mb-3">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4A6CF7" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
            Recommendations
          </h3>
          <ul className="space-y-1.5">
            {result.recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                <span className="text-brand-blue mt-0.5">&#x2022;</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
