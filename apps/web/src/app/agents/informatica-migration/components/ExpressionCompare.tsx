'use client';
import React, { useState, useMemo } from 'react';
import { ExpressionComparison } from '@/lib/types';

const PAGE_SIZE = 50;

const statusColor = (status: string) => {
  if (status === 'converted') return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
  if (status === 'partial') return 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300';
  return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300';
};

const cardBorder = (status: string) => {
  if (status === 'converted') return 'border-green-200 dark:border-green-800 bg-green-50/30 dark:bg-green-950/10';
  if (status === 'partial') return 'border-amber-200 dark:border-amber-800 bg-amber-50/30 dark:bg-amber-950/10';
  return 'border-red-200 dark:border-red-800 bg-red-50/30 dark:bg-red-950/10';
};

type StatusFilter = 'all' | 'converted' | 'partial' | 'failed';

export default function ExpressionCompare({ data }: { data: ExpressionComparison[] }) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');

  const counts = useMemo(() => ({
    all: data.length,
    converted: data.filter(e => e.status === 'converted').length,
    partial: data.filter(e => e.status === 'partial').length,
    failed: data.filter(e => e.status === 'failed').length,
  }), [data]);

  const filtered = useMemo(() => {
    let items = data;
    if (statusFilter !== 'all') items = items.filter(e => e.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(e =>
        e.mapping.toLowerCase().includes(q) ||
        e.original.toLowerCase().includes(q) ||
        e.converted.toLowerCase().includes(q)
      );
    }
    return items;
  }, [data, statusFilter, search]);

  const visible = filtered.slice(0, visibleCount);
  const hasMore = visibleCount < filtered.length;
  const convPct = counts.all > 0 ? Math.round((counts.converted / counts.all) * 100) : 0;

  return (
    <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">Expression Conversion Comparison</span>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Converted</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Partial</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Failed</span>
          </div>
        </div>

        {/* Summary stats */}
        <div className="flex items-center gap-4 mb-3">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-text-primary">
                {counts.converted} of {counts.all} expressions converted
              </span>
              <span className={`text-sm font-bold ${convPct >= 80 ? 'text-green-600' : convPct >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                {convPct}%
              </span>
            </div>
            <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-green-500 to-emerald-400 transition-all duration-700" style={{ width: `${convPct}%` }} />
            </div>
          </div>
        </div>

        {/* Filter tabs + search */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="inline-flex bg-surface-bg border border-surface-border rounded-lg overflow-hidden">
            {(['all', 'converted', 'partial', 'failed'] as StatusFilter[]).map(f => (
              <button
                key={f}
                onClick={() => { setStatusFilter(f); setVisibleCount(PAGE_SIZE); }}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === f
                    ? f === 'converted' ? 'bg-green-600 text-white'
                    : f === 'partial' ? 'bg-amber-600 text-white'
                    : f === 'failed' ? 'bg-red-600 text-white'
                    : 'bg-purple-600 text-white'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)} ({counts[f]})
              </button>
            ))}
          </div>
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search by mapping name or expression..."
              value={search}
              onChange={e => { setSearch(e.target.value); setVisibleCount(PAGE_SIZE); }}
              className="w-full px-3 py-1.5 text-xs bg-surface-card border border-surface-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-purple-500/30"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      {filtered.length === 0 ? (
        <div className="p-8 text-center text-sm text-text-muted">
          {search ? 'No expressions match your search.' : 'No expressions found to compare.'}
        </div>
      ) : (
        <div className="p-4 space-y-3 max-h-[600px] overflow-y-auto">
          {/* Count indicator */}
          <div className="text-xs text-text-muted mb-2">
            Showing {visible.length} of {filtered.length} expressions
            {statusFilter !== 'all' && ` (filtered: ${statusFilter})`}
          </div>

          {visible.map((ec, i) => (
            <div key={i} className={`p-3 rounded-lg border ${cardBorder(ec.status)}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono text-text-muted">{ec.mapping}</span>
                <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusColor(ec.status)}`}>{ec.status}</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] text-text-muted mb-1 uppercase tracking-wide flex items-center gap-1">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    Informatica
                  </div>
                  <code className="text-xs font-mono text-red-700 dark:text-red-300 break-all">{ec.original}</code>
                </div>
                <div>
                  <div className="text-[10px] text-text-muted mb-1 uppercase tracking-wide flex items-center gap-1">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    BigQuery
                  </div>
                  <code className="text-xs font-mono text-green-700 dark:text-green-300 break-all">{ec.converted}</code>
                </div>
              </div>
            </div>
          ))}

          {/* Load More */}
          {hasMore && (
            <button
              onClick={() => setVisibleCount(prev => prev + PAGE_SIZE)}
              className="w-full py-3 text-sm font-medium text-purple-600 hover:text-purple-700 bg-purple-50 dark:bg-purple-950/20 hover:bg-purple-100 dark:hover:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
              Show More ({filtered.length - visibleCount} remaining)
            </button>
          )}
        </div>
      )}
    </div>
  );
}
