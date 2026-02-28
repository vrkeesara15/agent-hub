'use client';
import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { InfoBanner } from '@/components/code-accelerator/InfoBanner';
import { ModeSelector } from '@/components/code-accelerator/ModeSelector';
import { CodeEditor } from '@/components/code-accelerator/CodeEditor';
import { ConversionChanges } from '@/components/code-accelerator/ConversionChanges';
import { SQLAnalysis } from '@/components/code-accelerator/SQLAnalysis';
import { Button } from '@/components/ui/Button';
import { convertCode, optimizeSQL, generateDAG } from '@/lib/api';
import { ConvertResponse, OptimizeResponse, NLToDAGResponse } from '@/lib/types';

const placeholders: Record<string, string> = {
  teradata_to_bigquery: `-- Paste your Teradata SQL here...
SELECT
  customer_id,
  ZEROIFNULL(revenue) AS revenue,
  CAST(order_date AS DATE FORMAT 'YYYY-MM-DD') AS order_date,
  CURRENT_DATE - 30 AS thirty_days_ago
FROM EDW_TABLES.CUSTOMER_ACCOUNT
WHERE order_date > CURRENT_DATE - 90
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) = 1;`,
  tableau_to_looker: `-- Paste your SQL to convert to LookML...
SELECT
  customer_id,
  customer_name,
  email,
  SUM(revenue) AS total_revenue,
  COUNT(order_id) AS order_count
FROM analytics.dim_customer
JOIN analytics.fact_orders USING (customer_id)
GROUP BY 1, 2, 3;`,
  sql_optimizer: `-- Paste your BigQuery SQL to analyze for performance...
SELECT *
FROM analytics.fact_sales
JOIN analytics.dim_customer ON fact_sales.customer_id = dim_customer.customer_id
ORDER BY sale_date DESC;`,
};

const TABLEAU_MIGRATION_URL = 'https://tableau-to-looker-migration-production.up.railway.app';

export default function CodeAcceleratorPage() {
  const [mode, setMode] = useState('teradata_to_bigquery');
  const [inputCode, setInputCode] = useState('');
  const [convertResult, setConvertResult] = useState<ConvertResponse | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResponse | null>(null);
  const [dagResult, setDagResult] = useState<NLToDAGResponse | null>(null);
  const [dagInput, setDagInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConvert = useCallback(async () => {
    if (mode === 'nl_to_dag') {
      if (!dagInput.trim()) return;
    } else {
      if (!inputCode.trim()) return;
    }
    setLoading(true);
    setError(null);
    setConvertResult(null);
    setOptimizeResult(null);
    setDagResult(null);

    try {
      if (mode === 'sql_optimizer') {
        const data = await optimizeSQL(inputCode);
        setOptimizeResult(data);
      } else if (mode === 'nl_to_dag') {
        const data = await generateDAG(dagInput);
        if (data.error) {
          setError(data.error);
        } else {
          setDagResult(data);
        }
      } else {
        const data = await convertCode(mode, inputCode);
        setConvertResult(data);
      }
    } catch {
      setError('Failed to process. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [mode, inputCode, dagInput]);

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    setConvertResult(null);
    setOptimizeResult(null);
    setDagResult(null);
    setError(null);
  };

  const downloadFile = (content: string, name: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const isOptimizer = mode === 'sql_optimizer';
  const isTableau = mode === 'tableau_to_looker';
  const isInformatica = mode === 'informatica_to_gcp';
  const isNLtoDAG = mode === 'nl_to_dag';

  const buttonLabel = () => {
    if (loading) {
      if (isOptimizer) return 'Analyzing...';
      if (isNLtoDAG) return 'Generating DAG...';
      return 'Converting...';
    }
    if (isOptimizer) return 'Analyze SQL';
    if (isNLtoDAG) return 'Generate DAG';
    return 'Convert';
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary tracking-wide">Gcp Launchpad</h1>
        </div>
        <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'Gcp Launchpad' }]} />
      </div>

      {/* Info Banner */}
      <div className="mb-6">
        <InfoBanner />
      </div>

      {/* Mode Selector */}
      <div className="mb-6">
        <ModeSelector mode={mode} onModeChange={handleModeChange} />
      </div>

      {/* Tableau Migration Tool Button */}
      {isTableau && (
        <div className="mb-6 p-4 bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-card flex items-center justify-between">
          <div>
            <p className="text-sm font-bold text-text-primary">Tableau Dashboard Migration Tool</p>
            <p className="text-xs text-text-secondary mt-1">
              Have a full Tableau dashboard to migrate? Use our dedicated migration tool for complete dashboard-to-Looker conversion.
            </p>
          </div>
          <a
            href={TABLEAU_MIGRATION_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 ml-4 inline-flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white rounded-button text-sm font-medium hover:bg-purple-700 transition-colors"
          >
            Open Migration Tool
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </a>
        </div>
      )}

      {/* ── Informatica Mode: Link to dedicated page ── */}
      {isInformatica && (
        <div className="mb-6 p-6 bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-card">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center flex-shrink-0">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <path d="M8 13h2l2 3 2-6 2 3h2"/>
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-text-primary mb-1">Informatica PowerCenter to GCP</h3>
              <p className="text-sm text-text-secondary mb-4">
                Upload your Informatica XML export to convert it into BigQuery SQL, Cloud Composer (Airflow) DAGs,
                transformation maps, and SCD MERGE statements. Includes a full migration report with download support.
              </p>
              <div className="flex flex-wrap gap-2 mb-4">
                {['XML to BigQuery', 'Airflow DAG', 'SCD MERGE', 'Transformation Map', 'Migration Report'].map((pill) => (
                  <span key={pill} className="text-xs px-2.5 py-1 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 rounded-full border border-indigo-200 dark:border-indigo-700">
                    {pill}
                  </span>
                ))}
              </div>
              <Link href="/agents/informatica-migration">
                <Button variant="primary" size="lg" className="px-8">
                  Open Informatica Migration
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ml-2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ── NL to DAG Mode ── */}
      {isNLtoDAG && (
        <div className="space-y-6">
          {/* Input */}
          <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
            <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50">
              <span className="text-xs font-medium text-text-secondary tracking-wide">Describe your pipeline in natural language</span>
            </div>
            <textarea
              value={dagInput}
              onChange={(e) => setDagInput(e.target.value)}
              placeholder="Describe your Airflow DAG pipeline... e.g., 'Extract data from BigQuery sales table, filter for Q1 records, aggregate revenue by region, load into analytics dataset, and send a Slack notification on completion'"
              className="w-full h-40 p-4 bg-transparent text-sm font-mono text-text-primary placeholder-text-muted resize-y focus:outline-none"
            />
          </div>

          {/* Generate Button */}
          <div className="flex justify-center">
            <Button
              variant="primary"
              size="lg"
              onClick={handleConvert}
              disabled={loading || !dagInput.trim()}
              className="px-12"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                  Generating DAG...
                </span>
              ) : 'Generate Airflow DAG'}
            </Button>
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {/* DAG Output */}
          {dagResult && !loading && (
            <div className="space-y-4">
              {/* Info bar */}
              <div className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-card">
                <div className="flex items-center gap-3">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16A34A" strokeWidth="2" strokeLinecap="round">
                    <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                  <div>
                    <span className="text-sm font-medium text-green-800 dark:text-green-300">DAG Generated Successfully</span>
                    <span className="text-xs text-green-600 dark:text-green-400 ml-3">
                      ID: {dagResult.dag_id} | File: {dagResult.filename}
                      {dagResult.used_llm ? ' | LLM-powered' : ' | Rule-based'}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => downloadFile(dagResult.dag_code, dagResult.filename)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-button text-xs font-medium bg-green-600 hover:bg-green-700 text-white transition-colors"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download .py
                  </button>
                  <button
                    onClick={() => navigator.clipboard.writeText(dagResult.dag_code)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-button text-xs font-medium border border-green-300 dark:border-green-700 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    Copy
                  </button>
                </div>
              </div>

              {/* Code output */}
              <div className="bg-surface-card border border-surface-border rounded-card overflow-hidden">
                <div className="px-4 py-3 border-b border-surface-border bg-surface-bg/50 flex items-center justify-between">
                  <span className="text-xs font-medium text-text-secondary tracking-wide">Generated Airflow DAG (Python)</span>
                  <span className="text-xs text-text-muted">{dagResult.filename}</span>
                </div>
                <pre className="p-4 text-sm font-mono text-text-primary overflow-x-auto max-h-[500px] overflow-y-auto whitespace-pre">
                  {dagResult.dag_code}
                </pre>
              </div>

              {/* Description */}
              {dagResult.description && (
                <div className="p-4 bg-surface-card border border-surface-border rounded-card">
                  <p className="text-xs font-medium text-text-secondary mb-1">Pipeline Description</p>
                  <p className="text-sm text-text-primary">{dagResult.description}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Standard modes: Code Panels ── */}
      {!isInformatica && !isNLtoDAG && (
        <>
          <div className={`grid grid-cols-1 ${isOptimizer ? '' : 'lg:grid-cols-2'} gap-6 mb-6`}>
            <CodeEditor
              label={isOptimizer ? 'SQL to Analyze' : 'Input'}
              value={inputCode}
              onChange={setInputCode}
              placeholder={placeholders[mode]}
            />
            {!isOptimizer && (
              <div className="relative">
                <CodeEditor
                  label={isTableau ? 'LookML Output' : 'Output'}
                  value={convertResult?.output_code || ''}
                  readOnly
                />
                {loading && (
                  <div className="absolute inset-0 bg-surface-card/80 rounded-card flex items-center justify-center">
                    <div className="flex flex-col items-center gap-3">
                      <svg className="animate-spin h-8 w-8 text-brand-blue" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                      </svg>
                      <span className="text-sm text-text-secondary">Converting...</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Action Button */}
          <div className="flex justify-center mb-8">
            <Button
              variant="primary"
              size="lg"
              onClick={handleConvert}
              disabled={loading || !inputCode.trim()}
              className="px-12"
            >
              {buttonLabel()}
            </Button>
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400 mb-6">
              {error}
            </div>
          )}

          {/* SQL Optimizer Results */}
          {isOptimizer && optimizeResult && !loading && (
            <SQLAnalysis result={optimizeResult} />
          )}

          {/* Conversion Results */}
          {!isOptimizer && convertResult && !loading && (
            <ConversionChanges
              changes={convertResult.changes}
              warnings={convertResult.warnings}
              completionPct={convertResult.completion_pct}
            />
          )}
        </>
      )}
    </div>
  );
}
