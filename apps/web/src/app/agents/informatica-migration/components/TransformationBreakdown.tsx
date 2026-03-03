'use client';
import React, { useMemo } from 'react';
import { TransformationMapItem } from '@/lib/types';

const TYPE_COLORS: Record<string, string> = {
  'Expression': '#6366F1',
  'Lookup Procedure': '#8B5CF6',
  'Source Qualifier': '#3B82F6',
  'Filter': '#06B6D4',
  'Output Transformation': '#10B981',
  'Mapplet': '#14B8A6',
  'Input Transformation': '#22D3EE',
  'Update Strategy': '#F59E0B',
  'Aggregator': '#EF4444',
  'Router': '#EC4899',
  'Sorter': '#F97316',
  'Sequence': '#84CC16',
  'Joiner': '#A855F7',
  'Custom Transformation': '#DC2626',
};

const CONVERSION_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  sql: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-300', label: 'SQL Convertible' },
  dataflow: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-300', label: 'Needs Dataflow' },
  manual: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-300', label: 'Manual Review' },
};

function getDefaultColor(index: number): string {
  const defaults = ['#64748B', '#94A3B8', '#475569', '#78716C', '#A1A1AA'];
  return defaults[index % defaults.length];
}

export default function TransformationBreakdown({ data }: { data: TransformationMapItem[] }) {
  const breakdown = useMemo(() => {
    const counts: Record<string, { count: number; type: string }> = {};
    data.forEach(item => {
      const key = item.informatica;
      if (!counts[key]) counts[key] = { count: 0, type: item.type };
      counts[key].count++;
    });
    return Object.entries(counts)
      .map(([name, { count, type }]) => ({ name, count, type }))
      .sort((a, b) => b.count - a.count);
  }, [data]);

  const total = data.length;
  const conversionSummary = useMemo(() => {
    const counts = { sql: 0, dataflow: 0, manual: 0 };
    data.forEach(item => {
      if (item.type === 'sql') counts.sql++;
      else if (item.type === 'dataflow') counts.dataflow++;
      else counts.manual++;
    });
    return counts;
  }, [data]);

  const maxCount = breakdown.length > 0 ? breakdown[0].count : 1;

  return (
    <div className="space-y-4">
      {/* Conversion summary cards */}
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(CONVERSION_COLORS).map(([key, style]) => {
          const count = conversionSummary[key as keyof typeof conversionSummary];
          const pct = total > 0 ? Math.round((count / total) * 100) : 0;
          return (
            <div key={key} className={`p-3 rounded-lg border border-surface-border ${style.bg}`}>
              <div className={`text-2xl font-bold ${style.text}`}>{count}</div>
              <div className="text-[10px] text-text-muted mt-0.5">{style.label}</div>
              <div className="w-full h-1 bg-gray-200 dark:bg-gray-700 rounded-full mt-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    key === 'sql' ? 'bg-green-500' : key === 'dataflow' ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className={`text-[10px] font-medium mt-1 ${style.text}`}>{pct}%</div>
            </div>
          );
        })}
      </div>

      {/* Horizontal bar chart */}
      <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50">
          <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">
            Transformation Types ({total} total)
          </span>
        </div>
        <div className="p-4 space-y-2.5">
          {breakdown.map((item, idx) => {
            const pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
            const barPct = maxCount > 0 ? Math.round((item.count / maxCount) * 100) : 0;
            const color = TYPE_COLORS[item.name] || getDefaultColor(idx);
            const convColor = item.type === 'sql' ? 'bg-green-500' : item.type === 'dataflow' ? 'bg-amber-500' : 'bg-red-500';

            return (
              <div key={item.name} className="group">
                <div className="flex items-center gap-3">
                  <div className="w-[180px] flex-shrink-0 flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-xs text-text-primary truncate">{item.name}</span>
                  </div>
                  <div className="flex-1 flex items-center gap-2">
                    <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden relative">
                      <div
                        className="h-full rounded transition-all duration-700 relative"
                        style={{ width: `${barPct}%`, backgroundColor: color, opacity: 0.8 }}
                      />
                    </div>
                    <span className="w-10 text-right text-xs font-bold text-text-primary">{item.count}</span>
                    <span className="w-10 text-right text-[10px] text-text-muted">{pct}%</span>
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${convColor}`} title={item.type} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
