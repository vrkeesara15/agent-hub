'use client';
import React from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { MessageCodeRequirements } from '@/lib/types';

interface RequirementsFormProps {
  requirements: MessageCodeRequirements;
  onChange: (reqs: MessageCodeRequirements) => void;
  onSubmit: () => void;
  loading: boolean;
}

const CHANNELS = ['email', 'push', 'sms', 'in-app'];
const CATEGORIES = [
  'onboarding',
  'transactional',
  'remarketing',
  'promotion',
  'lifecycle',
  'notification',
  'security',
];
const SCHEDULES = [
  'Daily 08:00 UTC',
  'Daily 10:00 UTC',
  'Every 2 hours',
  'Hourly',
  'Weekly Monday 10:00 UTC',
  'Real-time trigger',
];

function FormField({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-primary mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputClass =
  'w-full px-3 py-2 text-sm bg-surface-card border border-surface-border rounded-lg focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none text-text-primary placeholder:text-text-muted transition-colors';
const selectClass =
  'w-full px-3 py-2 text-sm bg-surface-card border border-surface-border rounded-lg focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none text-text-primary transition-colors';

export function RequirementsForm({
  requirements,
  onChange,
  onSubmit,
  loading,
}: RequirementsFormProps) {
  const update = (field: keyof MessageCodeRequirements, value: string) => {
    onChange({ ...requirements, [field]: value });
  };

  return (
    <Card>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950 flex items-center justify-center">
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
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </div>
        <div>
          <h2 className="text-base font-bold text-text-primary">
            Requirements
          </h2>
          <p className="text-xs text-text-muted">
            Define your new message code
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField label="Message Code" required>
          <input
            className={inputClass}
            value={requirements.message_code}
            onChange={(e) => update('message_code', e.target.value.toUpperCase())}
            placeholder="MC_YOUR_CODE"
          />
        </FormField>

        <FormField label="Name" required>
          <input
            className={inputClass}
            value={requirements.name}
            onChange={(e) => update('name', e.target.value)}
            placeholder="Human-readable name"
          />
        </FormField>

        <FormField label="Channel" required>
          <select
            className={selectClass}
            value={requirements.channel}
            onChange={(e) => update('channel', e.target.value)}
          >
            {CHANNELS.map((ch) => (
              <option key={ch} value={ch}>
                {ch.charAt(0).toUpperCase() + ch.slice(1)}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Category">
          <select
            className={selectClass}
            value={requirements.category}
            onChange={(e) => update('category', e.target.value)}
          >
            <option value="">Select category...</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Owner">
          <input
            className={inputClass}
            value={requirements.owner}
            onChange={(e) => update('owner', e.target.value)}
            placeholder="team-name"
          />
        </FormField>

        <FormField label="Schedule">
          <select
            className={selectClass}
            value={requirements.schedule}
            onChange={(e) => update('schedule', e.target.value)}
          >
            {SCHEDULES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </FormField>

        <div className="md:col-span-2">
          <FormField label="Description" required>
            <textarea
              className={`${inputClass} min-h-[72px] resize-y`}
              value={requirements.description}
              onChange={(e) => update('description', e.target.value)}
              placeholder="What does this message code do? Who should receive it?"
              rows={3}
            />
          </FormField>
        </div>

        <div className="md:col-span-2">
          <FormField label="Audience Rules">
            <textarea
              className={`${inputClass} min-h-[56px] resize-y`}
              value={requirements.audience_rules}
              onChange={(e) => update('audience_rules', e.target.value)}
              placeholder="e.g., Users who signed up in the last 7 days and have made at least 1 purchase"
              rows={2}
            />
          </FormField>
        </div>

        <FormField label="Exclusion Rules">
          <input
            className={inputClass}
            value={requirements.exclusion_rules}
            onChange={(e) => update('exclusion_rules', e.target.value)}
            placeholder="e.g., Exclude if messaged in last 7 days"
          />
        </FormField>

        <FormField label="Extra Fields">
          <input
            className={inputClass}
            value={requirements.extra_fields}
            onChange={(e) => update('extra_fields', e.target.value)}
            placeholder="e.g., product_name, discount_pct"
          />
        </FormField>
      </div>

      <div className="mt-6 flex justify-end">
        <Button
          variant="primary"
          size="lg"
          onClick={onSubmit}
          disabled={
            loading ||
            !requirements.message_code ||
            !requirements.name ||
            !requirements.description
          }
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
              Analyzing...
            </span>
          ) : (
            'Find Best Template'
          )}
        </Button>
      </div>
    </Card>
  );
}
