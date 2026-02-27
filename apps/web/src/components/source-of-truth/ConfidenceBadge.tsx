import React from 'react';

interface ConfidenceBadgeProps {
  level: 'high' | 'medium' | 'low';
}

export function ConfidenceBadge({ level }: ConfidenceBadgeProps) {
  const config = {
    high: { color: 'text-status-success border-status-success bg-green-50', icon: '✅', label: 'High Confidence' },
    medium: { color: 'text-status-warning border-status-warning bg-amber-50', icon: '⚠️', label: 'Medium Confidence' },
    low: { color: 'text-status-danger border-status-danger bg-red-50', icon: '❌', label: 'Low Confidence' },
  };

  const { color, label } = config[level];

  return (
    <div className="mt-6 flex justify-center">
      <span className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium border ${color}`}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" fill="#22C55E"/>
          <path d="M8 12l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        {label}
      </span>
    </div>
  );
}
