'use client';
import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { FileUpload } from '@/components/data-triage/FileUpload';
import { ScanResults } from '@/components/data-triage/ScanResults';
import { IssuesPanel } from '@/components/data-triage/IssuesPanel';
import { ActionBar } from '@/components/data-triage/ActionBar';
import { scanCode, fixTable } from '@/lib/api';
import { ScanResponse, FixResponse } from '@/lib/types';

export default function DataTriagePage() {
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fixResult, setFixResult] = useState<FixResponse | null>(null);
  const [scannedContent, setScannedContent] = useState('');

  const handleScan = useCallback(async (content: string, filename: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setFixResult(null);
    setScannedContent(content);
    try {
      const data = await scanCode(content, filename);
      setResult(data);
    } catch (err) {
      setError('Failed to scan. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleFix = useCallback(async (table: string) => {
    try {
      const data = await fixTable(table, scannedContent);
      setFixResult(data);
    } catch (err) {
      // silently fail
    }
  }, [scannedContent]);

  const handleScanAgain = () => {
    setResult(null);
    setFixResult(null);
    setError(null);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary uppercase tracking-wide">Check Data Health</h1>
        </div>
        <Breadcrumb items={[
          { label: 'Home', href: '/' },
          { label: 'Data Health Check' },
          ...(result ? [{ label: result.filename }] : []),
        ]} />
      </div>

      {/* Upload section (before results) */}
      {!result && !loading && (
        <FileUpload onScan={handleScan} loading={loading} />
      )}

      {/* Loading shimmer */}
      {loading && (
        <div className="space-y-4">
          <div className="h-6 shimmer rounded-md w-64" />
          <div className="h-10 shimmer rounded-md w-48" />
          <div className="h-64 shimmer rounded-card" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div>
          <ScanResults
            filename={result.filename}
            tablesFound={result.tables_found}
            tables={result.tables}
          />
          <IssuesPanel issues={result.issues} onFix={handleFix} />

          {/* Fix result modal/card */}
          {fixResult && (
            <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-card">
              <h4 className="text-sm font-bold text-text-primary mb-2">Fix Suggestion</h4>
              <p className="text-sm text-text-secondary mb-3">{fixResult.explanation}</p>
              <div className="font-mono text-sm space-y-1">
                <div className="text-red-500 line-through">{fixResult.original_line}</div>
                <div className="text-green-600">{fixResult.fixed_line}</div>
              </div>
            </div>
          )}

          <ActionBar onScanAgain={handleScanAgain} />
        </div>
      )}
    </div>
  );
}
