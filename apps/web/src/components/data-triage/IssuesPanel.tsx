'use client';
import React from 'react';
import { ScanIssue } from '@/lib/types';
import { Button } from '@/components/ui/Button';

interface IssuesPanelProps {
  issues: ScanIssue[];
  onFix?: (table: string) => void;
}

export function IssuesPanel({ issues, onFix }: IssuesPanelProps) {
  if (!issues || issues.length === 0) return null;

  return (
    <div className="mt-6">
      <div className="border-l-4 border-status-danger bg-alert-bg rounded-r-card p-5">
        <h4 className="text-sm font-bold text-status-danger uppercase tracking-wide mb-4 flex items-center gap-2">
          <span className="w-3 h-3 bg-status-danger rounded-full inline-block" />
          {issues.length} {issues.length === 1 ? 'Issue Needs' : 'Issues Need'} Attention
        </h4>
        <div className="space-y-3">
          {issues.map((issue, i) => (
            <div key={i} className="bg-surface-card rounded-card p-4 border border-red-100 dark:border-red-900">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-mono font-medium text-text-primary mb-1">{issue.table}</p>
                  <p className="text-sm text-text-secondary">{issue.message}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {issue.actions.includes('show_fix') && (
                    <Button variant="primary" size="sm" onClick={() => onFix?.(issue.table)}>
                      Show me how to fix
                    </Button>
                  )}
                  {issue.actions.includes('request_access') && (
                    <Button variant="primary" size="sm">
                      Request access
                    </Button>
                  )}
                  {issue.actions.includes('search_similar') && (
                    <Button variant="outline" size="sm">
                      Search similar
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
