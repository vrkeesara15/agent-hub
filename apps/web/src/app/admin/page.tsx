'use client';
import React from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/Card';

const agentMetrics = [
  {
    name: 'Object Iq',
    slug: 'source-of-truth',
    color: 'blue',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2" fill="#3B82F6"/>
      </svg>
    ),
    stats: [
      { label: 'Tables Indexed', value: '2,847', trend: '+12%' },
      { label: 'Queries Today', value: '142', trend: '+8%' },
      { label: 'Accuracy', value: '96%', trend: null },
    ],
    statusColor: 'bg-green-500',
    status: 'Active',
  },
  {
    name: 'Accelerated Cloud Migration',
    slug: 'code-accelerator',
    color: 'amber',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="1.5">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="#FDE68A"/>
      </svg>
    ),
    stats: [
      { label: 'Conversions Today', value: '89', trend: '+15%' },
      { label: 'Languages', value: '6', trend: null },
      { label: 'Avg Accuracy', value: '94%', trend: '+2%' },
    ],
    statusColor: 'bg-green-500',
    status: 'Active',
  },
  {
    name: 'Data Health & Observability',
    slug: 'data-triage',
    color: 'purple',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
      </svg>
    ),
    stats: [
      { label: 'Scans Today', value: '56', trend: '+5%' },
      { label: 'Issues Found', value: '23', trend: '-18%' },
      { label: 'Auto-Fixed', value: '18', trend: '+22%' },
    ],
    statusColor: 'bg-green-500',
    status: 'Active',
  },
  {
    name: 'Informatica Migration',
    slug: 'informatica-migration',
    color: 'indigo',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <path d="M8 13h2l2 3 2-6 2 3h2"/>
      </svg>
    ),
    stats: [
      { label: 'Migrations Today', value: '12', trend: '+33%' },
      { label: 'Transforms Converted', value: '87', trend: '+45%' },
      { label: 'SCD Patterns', value: '9', trend: null },
    ],
    statusColor: 'bg-green-500',
    status: 'Active',
  },
];

const informaticaBreakdown = [
  { label: 'XML Files Processed', value: 47, color: 'bg-indigo-500' },
  { label: 'BigQuery SQL Generated', value: 42, color: 'bg-green-500' },
  { label: 'Airflow DAGs Created', value: 38, color: 'bg-blue-500' },
  { label: 'SCD MERGE Statements', value: 15, color: 'bg-purple-500' },
  { label: 'Dataflow Required', value: 9, color: 'bg-amber-500' },
  { label: 'Manual Review Needed', value: 5, color: 'bg-red-500' },
];

const recentMigrations = [
  { file: 'wf_Customer_Dimension_Load.xml', complexity: 'medium', transforms: 7, status: 'complete', time: '5 min ago' },
  { file: 'wf_Invoice_ETL_Daily.xml', complexity: 'high', transforms: 14, status: 'complete', time: '12 min ago' },
  { file: 'wf_Product_Catalog_Sync.xml', complexity: 'low', transforms: 4, status: 'complete', time: '28 min ago' },
  { file: 'wf_Order_SCD2_Merge.xml', complexity: 'medium', transforms: 9, status: 'complete', time: '1 hr ago' },
  { file: 'wf_Finance_Aggregator.xml', complexity: 'high', transforms: 18, status: 'review', time: '2 hr ago' },
];

export default function AdminPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary tracking-wide">Dashboard & Configuration</h1>
        </div>
      </div>

      {/* ── Agent Metrics Grid ── */}
      <h2 className="text-sm font-bold text-text-primary tracking-wide mb-4 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        Agent Performance
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {agentMetrics.map((agent) => (
          <Link key={agent.slug} href={`/agents/${agent.slug}`}>
            <div className="bg-surface-card border border-surface-border rounded-card p-5 hover:border-brand-blue/30 hover:shadow-md transition-all cursor-pointer group">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  {agent.icon}
                  <span className="text-sm font-bold text-text-primary group-hover:text-brand-blue transition-colors">{agent.name}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${agent.statusColor}`} />
                  <span className="text-[10px] font-medium text-text-muted uppercase">{agent.status}</span>
                </div>
              </div>
              <div className="space-y-2.5">
                {agent.stats.map((stat) => (
                  <div key={stat.label} className="flex items-center justify-between">
                    <span className="text-xs text-text-secondary">{stat.label}</span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-bold text-text-primary">{stat.value}</span>
                      {stat.trend && (
                        <span className={`text-[10px] font-medium ${
                          stat.trend.startsWith('+') ? 'text-green-600' : 'text-red-500'
                        }`}>{stat.trend}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* ── Informatica Migration Dashboard ── */}
      <h2 className="text-sm font-bold text-text-primary tracking-wide mb-4 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        Informatica Migration Analytics
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Breakdown Chart */}
        <div className="lg:col-span-1 bg-surface-card border border-surface-border rounded-card p-5">
          <h3 className="text-sm font-bold text-text-primary mb-4">Migration Breakdown</h3>
          <div className="space-y-3">
            {informaticaBreakdown.map((item) => (
              <div key={item.label}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-text-secondary">{item.label}</span>
                  <span className="text-xs font-bold text-text-primary">{item.value}</span>
                </div>
                <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${item.color}`} style={{ width: `${(item.value / 50) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Migrations Table */}
        <div className="lg:col-span-2 bg-surface-card border border-surface-border rounded-card overflow-hidden">
          <div className="px-5 py-4 border-b border-surface-border">
            <h3 className="text-sm font-bold text-text-primary">Recent Informatica Migrations</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border bg-surface-bg/50">
                <th className="text-left py-2.5 px-5 text-text-secondary font-medium text-xs">File</th>
                <th className="text-left py-2.5 px-3 text-text-secondary font-medium text-xs">Complexity</th>
                <th className="text-center py-2.5 px-3 text-text-secondary font-medium text-xs">Transforms</th>
                <th className="text-left py-2.5 px-3 text-text-secondary font-medium text-xs">Status</th>
                <th className="text-right py-2.5 px-5 text-text-secondary font-medium text-xs">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentMigrations.map((m, i) => (
                <tr key={i} className="border-b border-surface-border/50 last:border-0 hover:bg-surface-bg/30 transition-colors">
                  <td className="py-3 px-5">
                    <span className="font-mono text-text-primary text-xs">{m.file}</span>
                  </td>
                  <td className="py-3 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                      m.complexity === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
                      m.complexity === 'medium' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' :
                      'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                    }`}>{m.complexity}</span>
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span className="text-xs font-bold text-text-primary">{m.transforms}</span>
                  </td>
                  <td className="py-3 px-3">
                    <span className="flex items-center gap-1.5">
                      <div className={`w-2 h-2 rounded-full ${
                        m.status === 'complete' ? 'bg-green-500' : 'bg-amber-500'
                      }`} />
                      <span className="text-xs text-text-secondary capitalize">{m.status}</span>
                    </span>
                  </td>
                  <td className="py-3 px-5 text-right">
                    <span className="text-xs text-text-muted">{m.time}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Conversion Health ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gradient-to-br from-green-50 to-emerald-50/50 dark:from-green-950/20 dark:to-emerald-950/10 border border-green-200 dark:border-green-800 rounded-card p-5 text-center">
          <div className="text-3xl font-bold text-green-600">89%</div>
          <div className="text-xs text-green-700 dark:text-green-400 mt-1 font-medium">Auto-Conversion Rate</div>
          <p className="text-[10px] text-green-600/70 mt-2">Transformations converted to BigQuery SQL automatically</p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50/50 dark:from-blue-950/20 dark:to-indigo-950/10 border border-blue-200 dark:border-blue-800 rounded-card p-5 text-center">
          <div className="text-3xl font-bold text-blue-600">32%</div>
          <div className="text-xs text-blue-700 dark:text-blue-400 mt-1 font-medium">SCD Detection Rate</div>
          <p className="text-[10px] text-blue-600/70 mt-2">Workflows with SCD patterns auto-detected</p>
        </div>
        <div className="bg-gradient-to-br from-amber-50 to-orange-50/50 dark:from-amber-950/20 dark:to-orange-950/10 border border-amber-200 dark:border-amber-800 rounded-card p-5 text-center">
          <div className="text-3xl font-bold text-amber-600">11%</div>
          <div className="text-xs text-amber-700 dark:text-amber-400 mt-1 font-medium">Manual Review Needed</div>
          <p className="text-[10px] text-amber-600/70 mt-2">Complex patterns requiring Dataflow or manual conversion</p>
        </div>
      </div>

      {/* ── Configuration Section ── */}
      <h2 className="text-sm font-bold text-text-primary tracking-wide mb-4 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
        Configuration
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <h3 className="text-sm font-bold text-text-primary mb-3">API Configuration</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Backend URL</label>
              <input
                type="text"
                defaultValue={process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
                className="w-full h-10 px-3 bg-surface-bg border border-surface-border rounded-button text-sm"
                readOnly
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Anthropic API Key Status</label>
              <span className="text-sm text-text-muted">Configure via backend environment variable</span>
            </div>
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-bold text-text-primary mb-3">Knowledge Base</h3>
          <p className="text-sm text-text-secondary">
            Upload CSV or Excel files to expand the knowledge base used by agents.
          </p>
          <p className="text-xs text-text-muted mt-2">
            Active sources: ug1_objects.csv, actuals.csv, frank_sheet.csv
          </p>
          <div className="mt-3 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-xs text-text-secondary">3 data sources loaded (7,540 total records)</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
