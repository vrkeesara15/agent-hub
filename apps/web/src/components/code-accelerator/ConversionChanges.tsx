import React from 'react';
import { ConversionChange, ConversionWarning } from '@/lib/types';

interface ConversionChangesProps {
  changes: ConversionChange[];
  warnings: ConversionWarning[];
  completionPct: number;
}

export function ConversionChanges({ changes, warnings, completionPct }: ConversionChangesProps) {
  return (
    <div className="space-y-4">
      {/* Completion indicator */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div className="h-full bg-brand-blue rounded-full transition-all" style={{ width: `${completionPct}%` }} />
        </div>
        <span className="text-sm font-medium text-text-secondary">{completionPct}% automated</span>
      </div>

      {/* Changes */}
      {changes.length > 0 && (
        <div>
          <h4 className="text-sm font-bold text-text-primary mb-3">Changes Applied</h4>
          <div className="space-y-2">
            {changes.map((change, i) => (
              <div key={i} className="p-3 bg-surface-card border border-surface-border rounded-card">
                <div className="flex items-start gap-3">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4A6CF7" strokeWidth="2" className="mt-0.5 flex-shrink-0">
                    <path d="M12 5v14M5 12h14"/>
                  </svg>
                  <div className="min-w-0">
                    <div className="text-xs font-mono mb-1">
                      <span className="text-red-500 line-through">{change.original}</span>
                      <span className="mx-2 text-text-muted">→</span>
                      <span className="text-green-600">{change.converted}</span>
                    </div>
                    <p className="text-xs text-text-muted">{change.explanation}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div>
          <h4 className="text-sm font-bold text-text-primary mb-3 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            VZ-Specific Notes
          </h4>
          <div className="space-y-2">
            {warnings.map((warning, i) => (
              <div key={i} className="p-3 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-card text-sm text-amber-800 dark:text-amber-400">
                <span className="font-medium">{warning.type}:</span> {warning.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
