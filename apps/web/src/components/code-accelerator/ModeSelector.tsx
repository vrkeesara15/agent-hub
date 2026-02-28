'use client';
import React from 'react';

interface ModeSelectorProps {
  mode: string;
  onModeChange: (mode: string) => void;
}

const modes = [
  { id: 'teradata_to_bigquery', label: 'Teradata \u2192 BigQuery' },
  { id: 'tableau_to_looker', label: 'Tableau \u2192 Looker' },
  { id: 'sql_optimizer', label: 'SQL Optimizer' },
  { id: 'informatica_to_gcp', label: 'Informatica \u2192 GCP' },
  { id: 'nl_to_dag', label: 'NL \u2192 Airflow DAG' },
];

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  return (
    <div className="flex items-center gap-1 bg-surface-card border border-surface-border rounded-card p-1 overflow-x-auto">
      {modes.map((m) => (
        <button
          key={m.id}
          onClick={() => onModeChange(m.id)}
          className={`flex-1 px-3 py-2.5 rounded-button text-sm font-medium transition-colors whitespace-nowrap ${
            mode === m.id
              ? 'bg-brand-blue text-white shadow-sm'
              : 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
