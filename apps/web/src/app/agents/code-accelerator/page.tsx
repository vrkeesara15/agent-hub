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
import { convertCode, optimizeSQL } from '@/lib/api';
import { ConvertResponse, OptimizeResponse } from '@/lib/types';

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConvert = useCallback(async () => {
    if (!inputCode.trim()) return;
    setLoading(true);
    setError(null);
    setConvertResult(null);
    setOptimizeResult(null);

    try {
      if (mode === 'sql_optimizer') {
        const data = await optimizeSQL(inputCode);
        setOptimizeResult(data);
      } else {
        const data = await convertCode(mode, inputCode);
        setConvertResult(data);
      }
    } catch {
      setError('Failed to process. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [mode, inputCode]);

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    setConvertResult(null);
    setOptimizeResult(null);
    setError(null);
  };

  const isOptimizer = mode === 'sql_optimizer';
  const isTableau = mode === 'tableau_to_looker';

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
          <h1 className="text-lg font-bold text-text-primary uppercase tracking-wide">Migrate to Google Cloud</h1>
        </div>
        <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'Migrate to Google Cloud' }]} />
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

      {/* Code Panels */}
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
          {loading
            ? (isOptimizer ? 'Analyzing...' : 'Converting...')
            : (isOptimizer ? 'Analyze SQL' : 'Convert')
          }
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
    </div>
  );
}
