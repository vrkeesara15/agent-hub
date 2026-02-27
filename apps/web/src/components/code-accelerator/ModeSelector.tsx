'use client';
import React from 'react';

interface ModeSelectorProps {
  mode: string;
  onModeChange: (mode: string) => void;
}

const modes = [
  { id: 'teradata_to_bigquery', label: 'Teradata → BigQuery' },
  { id: 'tableau_to_looker', label: 'Tableau → Looker' },
  { id: 'sql_optimizer', label: 'SQL Optimizer' },
];

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  return (
    <div className="flex items-center gap-1 bg-surface-card border border-surface-border rounded-card p-1">
      {modes.map((m) => (
        <button
          key={m.id}
          onClick={() => onModeChange(m.id)}
          className={`flex-1 px-4 py-2.5 rounded-button text-sm font-medium transition-colors ${
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
