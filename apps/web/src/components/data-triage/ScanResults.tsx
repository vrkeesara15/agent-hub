import React from 'react';
import { TableHealth } from '@/lib/types';

interface ScanResultsProps {
  filename: string;
  tablesFound: number;
  tables: TableHealth[];
}

const statusConfig = {
  healthy: { label: 'Healthy', icon: '\u2705', textClass: 'text-status-success', bgClass: 'bg-green-50 dark:bg-green-950' },
  warning: { label: 'Warning', icon: '\u26a0\ufe0f', textClass: 'text-status-warning', bgClass: 'bg-amber-50 dark:bg-amber-950' },
  alert: { label: 'Alert', icon: '\ud83d\udd34', textClass: 'text-status-danger', bgClass: 'bg-red-50 dark:bg-red-950' },
};

export function ScanResults({ filename, tablesFound, tables }: ScanResultsProps) {
  return (
    <div>
      {/* File header */}
      <div className="flex items-center gap-3 mb-4">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4A6CF7" strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <span className="text-sm text-text-secondary">Uploaded:</span>
        <span className="text-sm font-medium text-text-primary">{filename}</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" fill="#22C55E"/>
          <path d="M8 12l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>

      {/* Tables count */}
      <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide mb-4 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
        </svg>
        Tables Found in Your Code: {tablesFound}
      </h3>

      {/* Table grid */}
      <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800 border-b border-surface-border">
              <th className="text-left px-4 py-3 text-xs font-bold text-text-secondary uppercase tracking-wider">Table Name</th>
              <th className="text-left px-4 py-3 text-xs font-bold text-text-secondary uppercase tracking-wider">Status</th>
              <th className="text-left px-4 py-3 text-xs font-bold text-text-secondary uppercase tracking-wider">Issue</th>
            </tr>
          </thead>
          <tbody>
            {tables.map((table, i) => {
              const config = statusConfig[table.status];
              return (
                <tr key={i} className="border-b border-surface-border last:border-b-0 hover:bg-gray-50/50 dark:hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-sm font-mono text-text-primary">{table.name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${config.textClass}`}>
                      <span>{config.icon}</span>
                      {config.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-text-muted">
                    {table.issue || '\u2014'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
