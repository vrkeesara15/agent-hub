'use client';
import React from 'react';

interface CodeEditorProps {
  label: string;
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  placeholder?: string;
}

export function CodeEditor({ label, value, onChange, readOnly = false, placeholder }: CodeEditorProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 dark:bg-gray-800 border-b border-surface-border rounded-t-card">
        <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">{label}</span>
        {readOnly && value && (
          <button
            onClick={() => navigator.clipboard.writeText(value)}
            className="text-xs text-brand-blue hover:underline"
          >
            Copy
          </button>
        )}
      </div>
      <div className="flex-1 relative">
        {readOnly ? (
          <pre className="code-editor w-full h-full min-h-[300px] p-4 bg-surface-card border border-t-0 border-surface-border rounded-b-card overflow-auto whitespace-pre-wrap text-text-primary">
            {value || <span className="text-text-muted italic">Output will appear here...</span>}
          </pre>
        ) : (
          <textarea
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            placeholder={placeholder}
            className="code-editor w-full h-full min-h-[300px] p-4 bg-surface-card border border-t-0 border-surface-border rounded-b-card resize-none focus:outline-none focus:ring-2 focus:ring-brand-blue text-text-primary placeholder:text-text-muted"
            spellCheck={false}
          />
        )}
      </div>
    </div>
  );
}
