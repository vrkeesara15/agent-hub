import React from 'react';
import { TableAlternative } from '@/lib/types';

interface OtherTablesProps {
  tables: TableAlternative[];
}

export function OtherTables({ tables }: OtherTablesProps) {
  if (!tables || tables.length === 0) return null;

  return (
    <div className="mt-6">
      <h4 className="text-sm font-medium text-text-secondary mb-3">Other tables considered</h4>
      <div className="space-y-3">
        {tables.map((table) => (
          <div key={table.table_name} className="flex items-start gap-3 p-4 bg-surface-card border border-surface-border rounded-card">
            {table.status === 'deprecated' ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="mt-0.5 flex-shrink-0">
                <circle cx="12" cy="12" r="10" stroke="#EF4444" strokeWidth="2"/>
                <path d="M15 9l-6 6M9 9l6 6" stroke="#EF4444" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="mt-0.5 flex-shrink-0">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="#F59E0B" strokeWidth="2"/>
                <line x1="12" y1="9" x2="12" y2="13" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round"/>
                <line x1="12" y1="17" x2="12.01" y2="17" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            )}
            <div>
              <span className="text-sm font-medium text-text-primary">{table.table_name}</span>
              <span className="text-sm text-text-secondary"> — Not recommended. {table.reason}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
