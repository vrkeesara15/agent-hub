'use client';
import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type {
  MessageCodeGenerateResponse,
  MessageCodeDAGResponse,
} from '@/lib/types';

interface GeneratedOutputProps {
  result: MessageCodeGenerateResponse;
  dagResult: MessageCodeDAGResponse | null;
  onGenerateDAG: () => void;
  onSaveToKnowledge: () => void;
  onStartOver: () => void;
  dagLoading: boolean;
  saveLoading: boolean;
  saved: boolean;
}

type ActiveTab = 'sql' | 'changes' | 'dag';

export function GeneratedOutput({
  result,
  dagResult,
  onGenerateDAG,
  onSaveToKnowledge,
  onStartOver,
  dagLoading,
  saveLoading,
  saved,
}: GeneratedOutputProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('sql');
  const [copied, setCopied] = useState<string | null>(null);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const tabs: { id: ActiveTab; label: string }[] = [
    { id: 'sql', label: 'SQL' },
    { id: 'changes', label: `Changes (${result.changes.length})` },
    { id: 'dag', label: 'DAG' },
  ];

  return (
    <div className="space-y-4">
      {/* Header with logic summary */}
      <Card>
        <div className="flex items-start gap-3 mb-3">
          <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950 flex items-center justify-center flex-shrink-0">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#2563EB"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
              <polyline points="13 2 13 9 20 9" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-text-primary">
              Generated Message Code
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              Based on template:{' '}
              <span className="font-medium">{result.template_name}</span>
            </p>
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3 mb-3">
          <p className="text-xs text-text-secondary">
            <span className="font-medium">Logic:</span> {result.logic_summary}
          </p>
        </div>

        {result.warnings.length > 0 && (
          <div className="space-y-2 mb-3">
            {result.warnings.map((w, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#d97706"
                  strokeWidth="2"
                  className="flex-shrink-0 mt-0.5"
                >
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <p className="text-xs text-amber-800 dark:text-amber-200">
                  {w}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Tabbed content */}
      <Card padding={false}>
        <div className="flex border-b border-surface-border">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-brand-blue border-b-2 border-brand-blue'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {activeTab === 'sql' && (
            <div>
              <div className="flex justify-end mb-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(result.sql, 'sql')}
                >
                  {copied === 'sql' ? 'Copied!' : 'Copy SQL'}
                </Button>
              </div>
              <pre className="p-4 bg-gray-900 text-green-400 text-xs rounded-lg overflow-x-auto max-h-[500px] overflow-y-auto leading-relaxed">
                <code>{result.sql}</code>
              </pre>
            </div>
          )}

          {activeTab === 'changes' && (
            <div className="space-y-3">
              {result.changes.map((change, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg border border-surface-border"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2 py-0.5 text-[10px] font-medium rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                      {change.section}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary">
                    {change.description}
                  </p>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'dag' && (
            <div>
              {dagResult ? (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-text-muted">
                        DAG ID:{' '}
                        <span className="font-mono font-medium text-text-primary">
                          {dagResult.dag_id}
                        </span>
                      </span>
                      <span className="text-xs text-text-muted">
                        Cron:{' '}
                        <span className="font-mono font-medium text-text-primary">
                          {dagResult.cron}
                        </span>
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        copyToClipboard(dagResult.dag_code, 'dag')
                      }
                    >
                      {copied === 'dag' ? 'Copied!' : 'Copy DAG'}
                    </Button>
                  </div>
                  <pre className="p-4 bg-gray-900 text-green-400 text-xs rounded-lg overflow-x-auto max-h-[500px] overflow-y-auto leading-relaxed">
                    <code>{dagResult.dag_code}</code>
                  </pre>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12">
                  <p className="text-sm text-text-muted mb-4">
                    Generate the Airflow DAG for scheduling this message code
                  </p>
                  <Button
                    variant="primary"
                    onClick={onGenerateDAG}
                    disabled={dagLoading}
                  >
                    {dagLoading ? (
                      <span className="flex items-center gap-2">
                        <svg
                          className="animate-spin h-4 w-4"
                          viewBox="0 0 24 24"
                          fill="none"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                          />
                        </svg>
                        Generating DAG...
                      </span>
                    ) : (
                      'Generate Airflow DAG'
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={onStartOver}>
          Start Over
        </Button>
        <div className="flex gap-3">
          <Button
            variant="primary"
            onClick={onSaveToKnowledge}
            disabled={saveLoading || saved}
          >
            {saved
              ? 'Saved to Knowledge Base'
              : saveLoading
                ? 'Saving...'
                : 'Save to Knowledge Base'}
          </Button>
        </div>
      </div>
    </div>
  );
}
