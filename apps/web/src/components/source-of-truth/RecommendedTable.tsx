'use client';
import React, { useState } from 'react';
import { TableRecommendation } from '@/lib/types';
import { Button } from '@/components/ui/Button';

interface RecommendedTableProps {
  table: TableRecommendation;
}

export function RecommendedTable({ table }: RecommendedTableProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(table.table_name);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border-l-4 border-status-success bg-yellow-50 dark:bg-yellow-950 rounded-card p-6 shadow-card">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" fill="#22C55E"/>
          <path d="M8 12l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="text-sm font-bold text-status-success uppercase tracking-wide">Recommended Table</span>
      </div>

      {/* Table name */}
      <h3 className="text-xl font-bold text-brand-blue mb-4">{table.table_name}</h3>

      {/* Why section */}
      <div className="mb-4">
        <h4 className="text-xs font-bold text-text-primary uppercase tracking-wide mb-2">Why This Table:</h4>
        <ul className="space-y-1.5">
          {table.why.map((reason, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
              <span className="text-text-muted mt-0.5">•</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm text-text-secondary mb-5 flex-wrap">
        <span className="flex items-center gap-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
          {table.stats.row_count} rows
        </span>
        <span className="flex items-center gap-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          Last updated: {table.stats.last_updated}
        </span>
        <span className="flex items-center gap-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="#22C55E"/><path d="M8 12l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          Quality: {table.stats.quality_score}/100
        </span>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="primary" onClick={handleCopy}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          {copied ? 'Copied!' : 'Copy Table Name'}
        </Button>
        <Button variant="primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          Preview Data
        </Button>
        <Button variant="outline">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export
        </Button>
      </div>
    </div>
  );
}
