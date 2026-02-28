'use client';
import React from 'react';
import { AgentCard } from './AgentCard';
import { RecentActivity } from './RecentActivity';

function DatabaseIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
      <circle cx="18" cy="12" r="3" fill="none" stroke="#2563EB" strokeWidth="1.5"/>
      <path d="M18 11v2M17 12h2"/>
    </svg>
  );
}

function CodeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 18 22 12 16 6"/>
      <polyline points="8 6 2 12 8 18"/>
      <line x1="12" y1="2" x2="12" y2="22" strokeDasharray="2 2"/>
    </svg>
  );
}

function MonitorIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <path d="m21 21-4.3-4.3"/>
      <path d="M8 11h6M11 8v6"/>
    </svg>
  );
}

export function DashboardView() {
  return (
    <div className="space-y-8">
      {/* Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <AgentCard
          title="Object Iq"
          href="/agents/source-of-truth"
          icon={<DatabaseIcon />}
          status="active"
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-text-muted font-medium">Tables:</p>
              <p className="text-2xl font-bold text-text-primary">1,247</p>
            </div>
            <div>
              <p className="text-xs text-text-muted font-medium">Last scan:</p>
              <p className="text-2xl font-bold text-text-primary">2m ago</p>
            </div>
          </div>
        </AgentCard>

        <AgentCard
          title="Accelerated Cloud Migration"
          href="/agents/code-accelerator"
          icon={<CodeIcon />}
          status="active"
        >
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-surface-border text-text-secondary">
              Teradata→BQ
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-surface-border text-text-secondary">
              Tableau→Looker
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-surface-border text-text-secondary">
              SQL Optimizer
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-surface-border text-text-secondary">
              Informatica→GCP
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-surface-border text-text-secondary">
              NL→DAG
            </span>
          </div>
        </AgentCard>

        <AgentCard
          title="Data Health & Observability"
          href="/agents/data-triage"
          icon={<MonitorIcon />}
          status="active"
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-text-muted font-medium">Active Alerts:</p>
              <p className="text-2xl font-bold text-text-primary">3</p>
            </div>
            <div>
              <p className="text-xs text-text-muted font-medium">Pipelines:</p>
              <p className="text-2xl font-bold text-text-primary">47</p>
            </div>
          </div>
        </AgentCard>
      </div>

      {/* Recent Activity */}
      <RecentActivity />
    </div>
  );
}
