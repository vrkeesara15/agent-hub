'use client';
import React, { useState, useCallback } from 'react';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { Card } from '@/components/ui/Card';
import { RequirementsForm } from '@/components/message-code-builder/RequirementsForm';
import { TemplateReview } from '@/components/message-code-builder/TemplateReview';
import { GeneratedOutput } from '@/components/message-code-builder/GeneratedOutput';
import {
  analyzeMessageCodeRequirements,
  generateMessageCode,
  generateMessageCodeDAG,
  saveMessageCodeToKnowledge,
} from '@/lib/api';
import type {
  MessageCodeRequirements,
  MessageCodeAnalyzeResponse,
  MessageCodeGenerateResponse,
  MessageCodeDAGResponse,
} from '@/lib/types';

type Step = 'requirements' | 'template' | 'output';

const INITIAL_REQUIREMENTS: MessageCodeRequirements = {
  message_code: '',
  name: '',
  description: '',
  channel: 'email',
  category: '',
  owner: '',
  schedule: 'Daily 08:00 UTC',
  audience_rules: '',
  exclusion_rules: '',
  extra_fields: '',
};

const STEPS: { id: Step; label: string; num: number }[] = [
  { id: 'requirements', label: 'Requirements', num: 1 },
  { id: 'template', label: 'Template Match', num: 2 },
  { id: 'output', label: 'Generated Output', num: 3 },
];

export default function MessageCodeBuilderPage() {
  const [step, setStep] = useState<Step>('requirements');
  const [requirements, setRequirements] =
    useState<MessageCodeRequirements>(INITIAL_REQUIREMENTS);
  const [analysis, setAnalysis] =
    useState<MessageCodeAnalyzeResponse | null>(null);
  const [generateResult, setGenerateResult] =
    useState<MessageCodeGenerateResponse | null>(null);
  const [dagResult, setDagResult] =
    useState<MessageCodeDAGResponse | null>(null);

  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [generateLoading, setGenerateLoading] = useState(false);
  const [dagLoading, setDagLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = useCallback(async () => {
    setAnalyzeLoading(true);
    setError(null);
    try {
      const result = await analyzeMessageCodeRequirements(requirements);
      setAnalysis(result);
      setStep('template');
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to analyze requirements',
      );
    } finally {
      setAnalyzeLoading(false);
    }
  }, [requirements]);

  const handleGenerate = useCallback(
    async (templateId: string) => {
      setGenerateLoading(true);
      setError(null);
      try {
        const result = await generateMessageCode(requirements, templateId);
        setGenerateResult(result);
        setDagResult(null);
        setSaved(false);
        setStep('output');
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to generate message code',
        );
      } finally {
        setGenerateLoading(false);
      }
    },
    [requirements],
  );

  const handleGenerateDAG = useCallback(async () => {
    setDagLoading(true);
    setError(null);
    try {
      const result = await generateMessageCodeDAG(requirements);
      setDagResult(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to generate DAG',
      );
    } finally {
      setDagLoading(false);
    }
  }, [requirements]);

  const handleSave = useCallback(async () => {
    if (!generateResult) return;
    setSaveLoading(true);
    setError(null);
    try {
      await saveMessageCodeToKnowledge({
        message_code: requirements.message_code,
        name: requirements.name,
        description: requirements.description,
        channel: requirements.channel,
        category: requirements.category,
        owner: requirements.owner,
        schedule: requirements.schedule,
        sql: generateResult.sql,
        logic_summary: generateResult.logic_summary,
        tags: [
          requirements.channel,
          requirements.category,
        ].filter(Boolean),
      });
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to save to knowledge base',
      );
    } finally {
      setSaveLoading(false);
    }
  }, [requirements, generateResult]);

  const handleStartOver = useCallback(() => {
    setStep('requirements');
    setRequirements(INITIAL_REQUIREMENTS);
    setAnalysis(null);
    setGenerateResult(null);
    setDagResult(null);
    setSaved(false);
    setError(null);
  }, []);

  return (
    <div className="max-w-5xl mx-auto">
      <Breadcrumb
        items={[
          { label: 'Agents', href: '/' },
          { label: 'Message Code Builder' },
        ]}
      />

      {/* Header */}
      <div className="mt-4 mb-6">
        <h1 className="text-2xl font-bold text-text-primary">
          Message Code Builder
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Define requirements, pick a template, generate SQL + DAG, and build
          your knowledge base
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {STEPS.map((s, i) => (
          <React.Fragment key={s.id}>
            {i > 0 && (
              <div
                className={`flex-1 h-0.5 ${
                  STEPS.findIndex((x) => x.id === step) >= i
                    ? 'bg-brand-blue'
                    : 'bg-surface-border'
                }`}
              />
            )}
            <button
              onClick={() => {
                // Allow going back to previous steps
                const currentIdx = STEPS.findIndex((x) => x.id === step);
                const targetIdx = STEPS.findIndex((x) => x.id === s.id);
                if (targetIdx <= currentIdx) setStep(s.id);
              }}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                step === s.id
                  ? 'bg-brand-blue text-white'
                  : STEPS.findIndex((x) => x.id === step) >
                      STEPS.findIndex((x) => x.id === s.id)
                    ? 'bg-blue-100 text-brand-blue dark:bg-blue-950 cursor-pointer'
                    : 'bg-gray-100 text-text-muted dark:bg-gray-800'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  step === s.id
                    ? 'bg-white/20 text-white'
                    : STEPS.findIndex((x) => x.id === step) >
                        STEPS.findIndex((x) => x.id === s.id)
                      ? 'bg-brand-blue text-white'
                      : 'bg-gray-200 text-text-muted dark:bg-gray-700'
                }`}
              >
                {STEPS.findIndex((x) => x.id === step) >
                STEPS.findIndex((x) => x.id === s.id) ? (
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  s.num
                )}
              </span>
              {s.label}
            </button>
          </React.Fragment>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {/* Step content */}
      {step === 'requirements' && (
        <RequirementsForm
          requirements={requirements}
          onChange={setRequirements}
          onSubmit={handleAnalyze}
          loading={analyzeLoading}
        />
      )}

      {step === 'template' && analysis && (
        <TemplateReview
          analysis={analysis}
          onSelectTemplate={() => {}}
          onGenerate={handleGenerate}
          loading={generateLoading}
        />
      )}

      {step === 'output' && generateResult && (
        <GeneratedOutput
          result={generateResult}
          dagResult={dagResult}
          onGenerateDAG={handleGenerateDAG}
          onSaveToKnowledge={handleSave}
          onStartOver={handleStartOver}
          dagLoading={dagLoading}
          saveLoading={saveLoading}
          saved={saved}
        />
      )}
    </div>
  );
}
