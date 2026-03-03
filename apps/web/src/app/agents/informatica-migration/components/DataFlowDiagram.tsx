'use client';
import React, { useMemo, useState } from 'react';
import { MappingResult } from '@/lib/types';

const STATUS_COLORS: Record<string, { stroke: string; bg: string }> = {
  converted: { stroke: '#16A34A', bg: 'bg-green-50 dark:bg-green-950/20 border-green-300 dark:border-green-700' },
  partial: { stroke: '#D97706', bg: 'bg-amber-50 dark:bg-amber-950/20 border-amber-300 dark:border-amber-700' },
  failed: { stroke: '#DC2626', bg: 'bg-red-50 dark:bg-red-950/20 border-red-300 dark:border-red-700' },
};

interface Props {
  sources: string[];
  targets: string[];
  mappingResults: MappingResult[];
}

export default function DataFlowDiagram({ sources, targets, mappingResults }: Props) {
  const [showAll, setShowAll] = useState(false);

  // Determine overall status per target based on mapping results
  const targetStatus = useMemo(() => {
    const status: Record<string, string> = {};
    targets.forEach(t => {
      const tLower = t.toLowerCase();
      const related = mappingResults.filter(m =>
        m.mapping_name.toLowerCase().includes(tLower.replace(/^tgt_/i, '').substring(0, 10))
      );
      if (related.length === 0) {
        status[t] = 'converted'; // default — assume covered
      } else if (related.some(m => m.status === 'failed')) {
        status[t] = 'failed';
      } else if (related.some(m => m.status === 'partial')) {
        status[t] = 'partial';
      } else {
        status[t] = 'converted';
      }
    });
    return status;
  }, [targets, mappingResults]);

  const maxDisplay = showAll ? Math.max(sources.length, targets.length) : 12;
  const displaySources = sources.slice(0, maxDisplay);
  const displayTargets = targets.slice(0, maxDisplay);
  const hasMoreSources = sources.length > maxDisplay;
  const hasMoreTargets = targets.length > maxDisplay;

  const convCount = Object.values(targetStatus).filter(s => s === 'converted').length;
  const partCount = Object.values(targetStatus).filter(s => s === 'partial').length;
  const failCount = Object.values(targetStatus).filter(s => s === 'failed').length;

  return (
    <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50 flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">Data Flow: Source to Target</span>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Converted ({convCount})</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Partial ({partCount})</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Failed ({failCount})</span>
        </div>
      </div>

      <div className="p-6">
        <div className="flex items-stretch gap-4">
          {/* Sources column */}
          <div className="flex-1 space-y-2">
            <div className="text-[10px] font-bold text-blue-600 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>
              Sources ({sources.length})
            </div>
            {displaySources.map((src, i) => (
              <div key={i} className="px-3 py-2 rounded-lg border bg-blue-50 dark:bg-blue-950/20 border-blue-300 dark:border-blue-700 text-xs font-mono text-blue-800 dark:text-blue-300 truncate">
                {src}
              </div>
            ))}
            {hasMoreSources && !showAll && (
              <div className="text-[10px] text-text-muted text-center py-1">+{sources.length - maxDisplay} more</div>
            )}
          </div>

          {/* Arrow column */}
          <div className="flex flex-col items-center justify-center px-2 py-4">
            <div className="flex flex-col items-center gap-1">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-text-muted">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <div className="w-px h-full min-h-[60px] bg-gradient-to-b from-blue-400 via-purple-400 to-green-400" />
              <div className="text-[9px] text-text-muted text-center px-1 py-1 bg-surface-bg rounded border border-surface-border">
                {mappingResults.length} mappings
              </div>
              <div className="w-px h-full min-h-[60px] bg-gradient-to-b from-purple-400 to-green-400" />
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-text-muted">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>
          </div>

          {/* Targets column */}
          <div className="flex-1 space-y-2">
            <div className="text-[10px] font-bold text-green-600 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
              Targets ({targets.length})
            </div>
            {displayTargets.map((tgt, i) => {
              const status = targetStatus[tgt] || 'converted';
              const colors = STATUS_COLORS[status];
              return (
                <div key={i} className="flex items-center gap-2">
                  <div className={`flex-1 px-3 py-2 rounded-lg border text-xs font-mono truncate ${colors.bg}`}>
                    <span className={status === 'converted' ? 'text-green-800 dark:text-green-300' : status === 'partial' ? 'text-amber-800 dark:text-amber-300' : 'text-red-800 dark:text-red-300'}>
                      {tgt}
                    </span>
                  </div>
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: colors.stroke }} />
                </div>
              );
            })}
            {hasMoreTargets && !showAll && (
              <div className="text-[10px] text-text-muted text-center py-1">+{targets.length - maxDisplay} more</div>
            )}
          </div>
        </div>

        {/* Show all toggle */}
        {(sources.length > 12 || targets.length > 12) && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="mt-4 w-full py-2 text-xs font-medium text-purple-600 hover:text-purple-700 bg-purple-50 dark:bg-purple-950/20 hover:bg-purple-100 dark:hover:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-lg transition-colors"
          >
            {showAll ? 'Show Less' : `Show All (${sources.length} sources, ${targets.length} targets)`}
          </button>
        )}
      </div>
    </div>
  );
}
