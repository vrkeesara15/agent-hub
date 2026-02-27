'use client';
import React from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/Card';

export default function AdminPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          Back
        </Link>
        <span className="text-surface-border">|</span>
        <h1 className="text-lg font-bold text-text-primary uppercase tracking-wide">Admin Configuration</h1>
      </div>

      <div className="space-y-6">
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
            Supported: uc1_object_sheet.csv, table_mapping.csv, dag_inventory.csv
          </p>
        </Card>
      </div>
    </div>
  );
}
