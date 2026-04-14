'use client';
import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { MessageCodeAnalyzeResponse } from '@/lib/types';

interface TemplateReviewProps {
  analysis: MessageCodeAnalyzeResponse;
  onSelectTemplate: (templateId: string) => void;
  onGenerate: (templateId: string) => void;
  loading: boolean;
}

export function TemplateReview({
  analysis,
  onSelectTemplate,
  onGenerate,
  loading,
}: TemplateReviewProps) {
  const [selectedId, setSelectedId] = useState(
    analysis.recommended_template.id,
  );
  const [showTemplateSql, setShowTemplateSql] = useState(false);

  const rec = analysis.recommended_template;

  return (
    <div className="space-y-4">
      {/* Recommended template */}
      <Card>
        <div className="flex items-start gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-green-50 dark:bg-green-950 flex items-center justify-center flex-shrink-0">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#16a34a"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-sm font-bold text-text-primary">
                Recommended Template
              </h3>
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                Best Match
              </span>
            </div>
            <p className="text-xs text-text-muted mb-3">
              {analysis.match_reasoning}
            </p>
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-text-primary">
              {rec.name}
            </h4>
            <div className="flex gap-2">
              <span className="px-2 py-0.5 text-xs font-medium rounded-full border border-surface-border text-text-secondary">
                {rec.channel}
              </span>
              <span className="px-2 py-0.5 text-xs font-medium rounded-full border border-surface-border text-text-secondary">
                {rec.category}
              </span>
            </div>
          </div>
          <p className="text-xs text-text-muted mb-2">{rec.description}</p>
          {rec.logic_summary && (
            <p className="text-xs text-text-secondary">
              <span className="font-medium">Logic:</span> {rec.logic_summary}
            </p>
          )}
          {rec.tags && rec.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {rec.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 text-[10px] rounded bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Show/hide template SQL */}
        {rec.sql && (
          <div className="mb-4">
            <button
              onClick={() => setShowTemplateSql(!showTemplateSql)}
              className="text-xs text-brand-blue hover:underline flex items-center gap-1"
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={`transition-transform ${showTemplateSql ? 'rotate-90' : ''}`}
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
              {showTemplateSql ? 'Hide' : 'View'} template SQL
            </button>
            {showTemplateSql && (
              <pre className="mt-2 p-3 bg-gray-900 text-green-400 text-xs rounded-lg overflow-x-auto max-h-[300px] overflow-y-auto">
                <code>{rec.sql}</code>
              </pre>
            )}
          </div>
        )}

        <div className="flex gap-3">
          <Button
            variant="primary"
            onClick={() => onGenerate(rec.id)}
            disabled={loading}
          >
            {loading ? (
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
                Generating...
              </span>
            ) : (
              'Generate from this template'
            )}
          </Button>
        </div>
      </Card>

      {/* Alternatives */}
      {analysis.alternatives.length > 0 && (
        <Card>
          <h3 className="text-sm font-bold text-text-primary mb-3">
            Alternative Templates
          </h3>
          <div className="space-y-2">
            {analysis.alternatives.map((alt) => (
              <div
                key={alt.id}
                className={`flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer ${
                  selectedId === alt.id
                    ? 'border-brand-blue bg-blue-50 dark:bg-blue-950'
                    : 'border-surface-border hover:bg-gray-50 dark:hover:bg-gray-900'
                }`}
                onClick={() => {
                  setSelectedId(alt.id);
                  onSelectTemplate(alt.id);
                }}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">
                      {alt.name}
                    </span>
                    <span className="px-1.5 py-0.5 text-[10px] rounded border border-surface-border text-text-muted">
                      {alt.channel}
                    </span>
                  </div>
                  <p className="text-xs text-text-muted mt-0.5">
                    {alt.description}
                  </p>
                </div>
                {selectedId === alt.id && selectedId !== rec.id && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onGenerate(alt.id);
                    }}
                    disabled={loading}
                  >
                    Use this
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
