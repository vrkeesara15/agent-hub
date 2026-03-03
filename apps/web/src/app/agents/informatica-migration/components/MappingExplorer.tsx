'use client';
import React, { useState, useMemo } from 'react';
import { MappingResult } from '@/lib/types';

const statusColor = (status: string) => {
  if (status === 'converted') return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
  if (status === 'partial') return 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300';
  return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300';
};

type SortKey = 'status' | 'name' | 'complexity';

export default function MappingExplorer({ data }: { data: MappingResult[] }) {
  const [expandedIdx, setExpandedIdx] = useState<Set<number>>(new Set());
  const [sortBy, setSortBy] = useState<SortKey>('status');
  const [search, setSearch] = useState('');
  const [showFullSql, setShowFullSql] = useState<number | null>(null);

  const counts = useMemo(() => ({
    converted: data.filter(m => m.status === 'converted').length,
    partial: data.filter(m => m.status === 'partial').length,
    failed: data.filter(m => m.status === 'failed').length,
  }), [data]);

  const statusOrder: Record<string, number> = { failed: 0, partial: 1, converted: 2 };

  const sorted = useMemo(() => {
    let items = [...data];
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(m => m.mapping_name.toLowerCase().includes(q));
    }
    items.sort((a, b) => {
      if (sortBy === 'status') return (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9);
      if (sortBy === 'name') return a.mapping_name.localeCompare(b.mapping_name);
      return b.transformations_used - a.transformations_used;
    });
    return items;
  }, [data, sortBy, search]);

  const toggle = (idx: number) => {
    setExpandedIdx(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const getSqlPreview = (sql: string) => {
    const lines = sql.split('\n').filter(l => l.trim());
    return lines.slice(0, 8).join('\n');
  };

  return (
    <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
      {/* Header with summary */}
      <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">Mapping Explorer</span>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              {counts.converted} converted
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300">
              {counts.partial} partial
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
              {counts.failed} failed
            </span>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-text-muted uppercase">Sort:</span>
            {(['status', 'name', 'complexity'] as SortKey[]).map(s => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  sortBy === s ? 'bg-purple-600 text-white' : 'bg-surface-bg border border-surface-border text-text-secondary hover:text-text-primary'
                }`}
              >
                {s === 'status' ? 'Status' : s === 'name' ? 'Name' : 'Complexity'}
              </button>
            ))}
          </div>
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search mappings..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-surface-card border border-surface-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-purple-500/30"
            />
          </div>
        </div>
      </div>

      {/* Mapping rows */}
      <div className="divide-y divide-surface-border/50 max-h-[700px] overflow-y-auto">
        {sorted.map((mr, i) => {
          const isExpanded = expandedIdx.has(i);
          const isFullSql = showFullSql === i;
          const tPct = mr.transformations_used > 0 ? Math.round((mr.transformations_converted / mr.transformations_used) * 100) : 0;
          const ePct = mr.expressions_total > 0 ? Math.round((mr.expressions_converted / mr.expressions_total) * 100) : 0;

          return (
            <div key={i}>
              {/* Collapsed row */}
              <button
                onClick={() => toggle(i)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-bg/30 transition-colors text-left"
              >
                <svg
                  width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  className={`flex-shrink-0 text-text-muted transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-xs text-text-primary truncate block">{mr.mapping_name}</span>
                </div>
                <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-medium ${statusColor(mr.status)}`}>{mr.status}</span>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-text-secondary">
                    <span className="text-green-600 font-medium">{mr.transformations_converted}</span>
                    <span className="text-text-muted">/{mr.transformations_used} transforms</span>
                  </span>
                  <span className="text-text-secondary">
                    <span className="text-blue-600 font-medium">{mr.expressions_converted}</span>
                    <span className="text-text-muted">/{mr.expressions_total} expr</span>
                  </span>
                  {mr.used_llm
                    ? <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">LLM</span>
                    : <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">Rules</span>
                  }
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 ml-7 space-y-3 animate-in fade-in duration-200">
                  {/* Progress bars */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="flex items-center justify-between text-[10px] mb-1">
                        <span className="text-text-muted">Transformations</span>
                        <span className={`font-bold ${tPct >= 80 ? 'text-green-600' : tPct >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{tPct}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${tPct >= 80 ? 'bg-green-500' : tPct >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${tPct}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between text-[10px] mb-1">
                        <span className="text-text-muted">Expressions</span>
                        <span className={`font-bold ${ePct >= 80 ? 'text-green-600' : ePct >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{ePct}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${ePct >= 80 ? 'bg-green-500' : ePct >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${ePct}%` }} />
                      </div>
                    </div>
                  </div>

                  {/* Issues */}
                  {mr.issues.length > 0 && (
                    <div className="p-2.5 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                      <div className="text-[10px] text-amber-700 dark:text-amber-400 font-medium uppercase mb-1.5 flex items-center gap-1">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        Issues ({mr.issues.length})
                      </div>
                      {mr.issues.map((issue, j) => (
                        <div key={j} className="text-xs text-amber-800 dark:text-amber-300 py-0.5">{issue}</div>
                      ))}
                    </div>
                  )}

                  {/* SQL Preview */}
                  {mr.sql && (
                    <div className="bg-gray-900 dark:bg-gray-950 rounded-lg overflow-hidden border border-gray-700">
                      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 dark:bg-gray-900 border-b border-gray-700">
                        <span className="text-[10px] text-gray-400 uppercase tracking-wide">Generated BigQuery SQL</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(mr.sql); }}
                            className="text-[10px] text-gray-400 hover:text-gray-200 transition-colors"
                          >
                            Copy
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); setShowFullSql(isFullSql ? null : i); }}
                            className="text-[10px] text-purple-400 hover:text-purple-300 transition-colors"
                          >
                            {isFullSql ? 'Collapse' : 'View Full SQL'}
                          </button>
                        </div>
                      </div>
                      <pre className={`p-3 text-xs font-mono text-gray-300 overflow-x-auto ${isFullSql ? 'max-h-[400px]' : 'max-h-[180px]'} overflow-y-auto whitespace-pre`}>
                        {isFullSql ? mr.sql : getSqlPreview(mr.sql)}
                        {!isFullSql && mr.sql.split('\n').length > 8 && (
                          <span className="text-gray-500">{'\n'}... ({mr.sql.split('\n').length - 8} more lines)</span>
                        )}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer summary */}
      <div className="px-4 py-2.5 border-t border-surface-border bg-surface-bg/50 text-xs text-text-muted">
        {sorted.length} of {data.length} mappings shown
        {search && ` (filtered by "${search}")`}
      </div>
    </div>
  );
}
