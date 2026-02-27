'use client';
import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { InfoBanner } from '@/components/code-accelerator/InfoBanner';
import { ModeSelector } from '@/components/code-accelerator/ModeSelector';
import { CodeEditor } from '@/components/code-accelerator/CodeEditor';
import { ConversionChanges } from '@/components/code-accelerator/ConversionChanges';
import { Button } from '@/components/ui/Button';
import { convertCode } from '@/lib/api';
import { ConvertResponse } from '@/lib/types';

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
  tableau_to_looker: '-- Paste your Tableau calculated field or describe the dashboard structure...',
  sql_optimizer: '-- Paste your BigQuery SQL to optimize...',
};

export default function CodeAcceleratorPage() {
  const [mode, setMode] = useState('teradata_to_bigquery');
  const [inputCode, setInputCode] = useState('');
  const [result, setResult] = useState<ConvertResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConvert = useCallback(async () => {
    if (!inputCode.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await convertCode(mode, inputCode);
      setResult(data);
    } catch (err) {
      setError('Failed to convert. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [mode, inputCode]);

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    setResult(null);
    setError(null);
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
          <h1 className="text-lg font-bold text-text-primary uppercase tracking-wide">Convert Your Code</h1>
        </div>
        <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'Convert Your Code' }]} />
      </div>

      {/* Info Banner */}
      <div className="mb-6">
        <InfoBanner />
      </div>

      {/* Mode Selector */}
      <div className="mb-6">
        <ModeSelector mode={mode} onModeChange={handleModeChange} />
      </div>

      {/* Code Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <CodeEditor
          label="Input"
          value={inputCode}
          onChange={setInputCode}
          placeholder={placeholders[mode]}
        />
        <div className="relative">
          <CodeEditor
            label="Output"
            value={result?.output_code || ''}
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
      </div>

      {/* Convert Button */}
      <div className="flex justify-center mb-8">
        <Button
          variant="primary"
          size="lg"
          onClick={handleConvert}
          disabled={loading || !inputCode.trim()}
          className="px-12"
        >
          {loading ? 'Converting...' : 'Convert'}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400 mb-6">
          {error}
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <ConversionChanges
          changes={result.changes}
          warnings={result.warnings}
          completionPct={result.completion_pct}
        />
      )}
    </div>
  );
}
