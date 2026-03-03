'use client';
import React from 'react';
import { MigrationScorecard, MappingResult, TransformationMapItem, ExpressionComparison } from '@/lib/types';
import TransformationBreakdown from './TransformationBreakdown';

function CircularProgress({ value, size = 140, strokeWidth = 10, color }: { value: number; size?: number; strokeWidth?: number; color?: string }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const c = color || (value >= 80 ? '#16A34A' : value >= 50 ? '#D97706' : '#DC2626');

  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={strokeWidth} className="text-gray-200 dark:text-gray-700" />
      <circle
        cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={c} strokeWidth={strokeWidth}
        strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
        className="transition-all duration-1000 ease-out"
      />
    </svg>
  );
}

function MiniRing({ value, size = 48, strokeWidth = 4 }: { value: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const c = value >= 80 ? '#16A34A' : value >= 50 ? '#D97706' : '#DC2626';

  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={strokeWidth} className="text-gray-200 dark:text-gray-700" />
      <circle
        cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={c} strokeWidth={strokeWidth}
        strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
        className="transition-all duration-1000 ease-out"
      />
    </svg>
  );
}

const scoreLabel = (v: number) => v >= 90 ? 'Excellent' : v >= 80 ? 'Good' : v >= 60 ? 'Fair' : v >= 40 ? 'Needs Work' : 'Critical';
const scoreLabelColor = (v: number) => v >= 80 ? 'text-green-600' : v >= 50 ? 'text-amber-600' : 'text-red-600';
const scoreBgColor = (score: number) => {
  if (score >= 80) return 'bg-green-100 dark:bg-green-900/30 border-green-200 dark:border-green-800';
  if (score >= 50) return 'bg-amber-100 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800';
  return 'bg-red-100 dark:bg-red-900/30 border-red-200 dark:border-red-800';
};

interface Props {
  scorecard: MigrationScorecard;
  mappingResults: MappingResult[];
  transformationMap: TransformationMapItem[];
  sources: string[];
  targets: string[];
  expressionComparisons: ExpressionComparison[];
}

export default function ScorecardEnhanced({ scorecard: sc, mappingResults, transformationMap, sources, targets, expressionComparisons }: Props) {
  const dims = [
    { label: 'SQL Coverage', value: sc.sql_coverage, desc: 'Mappings with generated SQL', icon: <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" /> },
    { label: 'Target Coverage', value: sc.target_coverage, desc: 'Target tables addressed', icon: <><rect x="3" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></> },
    { label: 'Expression Fidelity', value: sc.expression_fidelity, desc: 'Expressions converted', icon: <path d="M22 12h-4l-3 9L9 3l-3 9H2" /> },
    { label: 'DAG Completeness', value: sc.dag_completeness, desc: 'Mappings with DAG tasks', icon: <><circle cx="12" cy="12" r="3" /><path d="M12 1v4M12 19v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M1 12h4M19 12h4" /></> },
    { label: 'Param Resolution', value: sc.parameter_resolution, desc: '$$params resolved', icon: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4" /></> },
    { label: 'SCD Coverage', value: sc.scd_coverage, desc: 'SCD patterns handled', icon: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /> },
  ];

  const converted = mappingResults.filter(m => m.status === 'converted').length;
  const partial = mappingResults.filter(m => m.status === 'partial').length;
  const failed = mappingResults.filter(m => m.status === 'failed').length;
  const exprConverted = expressionComparisons.filter(e => e.status === 'converted').length;

  // Migration readiness items
  const readiness: { label: string; ready: boolean; detail: string }[] = [
    { label: 'BigQuery SQL', ready: sc.sql_coverage >= 70, detail: `${sc.sql_coverage}% of mappings have generated SQL` },
    { label: 'Airflow DAG', ready: sc.dag_completeness >= 70, detail: `${sc.dag_completeness}% of mappings have DAG tasks` },
    { label: 'Target Tables', ready: sc.target_coverage >= 70, detail: `${sc.target_coverage}% of target tables addressed` },
    { label: 'Expression Logic', ready: sc.expression_fidelity >= 60, detail: `${sc.expression_fidelity}% of expressions converted` },
    { label: 'Parameters', ready: sc.parameter_resolution >= 50, detail: `${sc.parameter_resolution}% of $$params resolved` },
    { label: 'SCD Patterns', ready: sc.scd_coverage >= 80, detail: `${sc.scd_coverage}% of SCD patterns handled` },
  ];

  return (
    <div className="space-y-6">
      {/* Main score with circular progress */}
      <div className={`p-6 rounded-card border-2 ${scoreBgColor(sc.overall_score)} relative overflow-hidden`}>
        <div className="flex items-center justify-center gap-8">
          <div className="relative">
            <CircularProgress value={sc.overall_score} size={160} strokeWidth={12} />
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className={`text-4xl font-black ${scoreLabelColor(sc.overall_score)}`}>{sc.overall_score}%</div>
              <div className={`text-xs font-medium ${scoreLabelColor(sc.overall_score)}`}>{scoreLabel(sc.overall_score)}</div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="text-lg font-bold text-text-primary">Overall Migration Score</div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div><span className="font-bold text-purple-600">{mappingResults.length}</span> <span className="text-text-muted">mappings processed</span></div>
              <div><span className="font-bold text-green-600">{converted}</span> <span className="text-text-muted">fully converted</span></div>
              <div><span className="font-bold text-blue-600">{sources.length}</span> <span className="text-text-muted">sources mapped</span></div>
              <div><span className="font-bold text-indigo-600">{targets.length}</span> <span className="text-text-muted">targets addressed</span></div>
              <div><span className="font-bold text-green-600">{exprConverted}</span> <span className="text-text-muted">expressions converted</span></div>
              <div><span className="font-bold text-amber-600">{partial + failed}</span> <span className="text-text-muted">need review</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* Dimension scores with mini rings */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {dims.map((d) => (
          <div key={d.label} className="p-4 bg-surface-card border border-surface-border rounded-card">
            <div className="flex items-start gap-3">
              <div className="relative flex-shrink-0">
                <MiniRing value={d.value} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={`text-[11px] font-bold ${scoreLabelColor(d.value)}`}>{d.value}</span>
                </div>
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-text-primary">{d.label}</div>
                <div className={`text-[10px] font-medium ${scoreLabelColor(d.value)}`}>{scoreLabel(d.value)}</div>
                <div className="text-[10px] text-text-muted mt-0.5">{d.desc}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3 bg-surface-card border border-surface-border rounded-card text-center">
          <div className="text-lg font-bold text-purple-600">{mappingResults.length}</div>
          <div className="text-[10px] text-text-muted">Mappings Processed</div>
        </div>
        <div className="p-3 bg-surface-card border border-surface-border rounded-card text-center">
          <div className="text-lg font-bold text-green-600">{converted}</div>
          <div className="text-[10px] text-text-muted">Fully Converted</div>
        </div>
        <div className="p-3 bg-surface-card border border-surface-border rounded-card text-center">
          <div className="text-lg font-bold text-blue-600">{expressionComparisons.length}</div>
          <div className="text-[10px] text-text-muted">Expressions Analyzed</div>
        </div>
        <div className="p-3 bg-surface-card border border-surface-border rounded-card text-center">
          <div className="text-lg font-bold text-indigo-600">{transformationMap.length}</div>
          <div className="text-[10px] text-text-muted">Transformations Mapped</div>
        </div>
      </div>

      {/* Migration Readiness */}
      <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50">
          <span className="text-xs font-medium text-text-secondary uppercase tracking-wide">Migration Readiness Assessment</span>
        </div>
        <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3">
          {readiness.map(r => (
            <div key={r.label} className={`p-3 rounded-lg border flex items-start gap-2.5 ${r.ready ? 'border-green-200 dark:border-green-800 bg-green-50/30 dark:bg-green-950/10' : 'border-amber-200 dark:border-amber-800 bg-amber-50/30 dark:bg-amber-950/10'}`}>
              {r.ready ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round" className="flex-shrink-0 mt-0.5"><path d="M22 11.08V12a10 10 0 11-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2" className="flex-shrink-0 mt-0.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
              )}
              <div>
                <div className={`text-xs font-semibold ${r.ready ? 'text-green-700 dark:text-green-300' : 'text-amber-700 dark:text-amber-300'}`}>{r.label}</div>
                <div className="text-[10px] text-text-muted">{r.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Transformation Breakdown Chart */}
      {transformationMap.length > 0 && (
        <TransformationBreakdown data={transformationMap} />
      )}
    </div>
  );
}
