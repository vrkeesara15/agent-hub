'use client';
import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/Button';

interface FileUploadProps {
  onScan: (content: string, filename: string) => void;
  loading?: boolean;
}

export function FileUpload({ onScan, loading = false }: FileUploadProps) {
  const [filename, setFilename] = useState('');
  const [content, setContent] = useState('');
  const [gitUrl, setGitUrl] = useState('');
  const [mode, setMode] = useState<'file' | 'paste' | 'git'>('paste');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFilename(file.name);
      const reader = new FileReader();
      reader.onload = (ev) => {
        setContent(ev.target?.result as string);
      };
      reader.readAsText(file);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      setFilename(file.name);
      const reader = new FileReader();
      reader.onload = (ev) => {
        setContent(ev.target?.result as string);
      };
      reader.readAsText(file);
    }
  };

  const handleScan = () => {
    if (content.trim()) {
      onScan(content, filename || 'pasted_code.sql');
    }
  };

  const sampleSQL = `-- Sample: sales_report_pipeline.sql
SELECT
  s.order_id,
  s.revenue,
  c.customer_name,
  c.email,
  p.product_name,
  d.fiscal_quarter
FROM analytics.fact_sales s
JOIN analytics.dim_customer c ON s.customer_id = c.customer_id
JOIN analytics.dim_product p ON s.product_id = p.product_id
JOIN analytics.dim_date d ON s.order_date = d.date_key
LEFT JOIN staging.temp_orders t ON s.order_id = t.order_id
LEFT JOIN legacy.old_customers lc ON s.legacy_id = lc.id
LEFT JOIN reports.summary_cache rc ON s.report_id = rc.cache_id
WHERE d.fiscal_year = 2024;`;

  return (
    <div className="space-y-4">
      {/* Mode tabs */}
      <div className="flex items-center gap-1 bg-surface-card border border-surface-border rounded-button p-1 w-fit">
        {(['paste', 'file', 'git'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
              mode === m ? 'bg-brand-blue text-white' : 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}
          >
            {m === 'paste' ? 'Paste SQL' : m === 'file' ? 'Upload File' : 'Git Link'}
          </button>
        ))}
      </div>

      {mode === 'file' && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-surface-border rounded-card p-8 text-center cursor-pointer hover:border-brand-blue hover:bg-blue-50/30 transition-colors"
        >
          <input ref={fileRef} type="file" accept=".sql,.txt" onChange={handleFileChange} className="hidden" />
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" className="mx-auto mb-3">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <polyline points="9 15 12 12 15 15"/>
          </svg>
          <p className="text-sm text-text-secondary">
            {filename ? (
              <span className="text-brand-blue font-medium">{filename}</span>
            ) : (
              <>Drop your SQL file here or <span className="text-brand-blue font-medium">browse</span></>
            )}
          </p>
        </div>
      )}

      {mode === 'paste' && (
        <div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste your SQL code here..."
            className="code-editor w-full h-64 p-4 bg-surface-card border border-surface-border rounded-card resize-none focus:outline-none focus:ring-2 focus:ring-brand-blue text-text-primary placeholder:text-text-muted"
            spellCheck={false}
          />
          {!content && (
            <button
              onClick={() => { setContent(sampleSQL); setFilename('sales_report_pipeline.sql'); }}
              className="mt-2 text-xs text-brand-blue hover:underline"
            >
              Load sample SQL for demo
            </button>
          )}
        </div>
      )}

      {mode === 'git' && (
        <div className="flex gap-3">
          <input
            type="text"
            value={gitUrl}
            onChange={(e) => setGitUrl(e.target.value)}
            placeholder="https://github.com/org/repo/blob/main/pipeline.sql"
            className="flex-1 h-11 px-4 bg-surface-card border border-surface-border rounded-button text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
          />
        </div>
      )}

      <Button
        variant="primary"
        size="lg"
        onClick={handleScan}
        disabled={loading || !content.trim()}
      >
        {loading ? (
          <div className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            Scanning...
          </div>
        ) : 'Scan'}
      </Button>
    </div>
  );
}
