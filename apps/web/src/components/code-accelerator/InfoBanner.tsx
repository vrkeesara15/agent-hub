import React from 'react';

export function InfoBanner() {
  return (
    <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-card p-4 flex items-start gap-3">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4A6CF7" strokeWidth="2" className="flex-shrink-0 mt-0.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 16v-4M12 8h.01"/>
      </svg>
      <p className="text-sm text-blue-800 dark:text-blue-300">
        This accelerator gets you 70-80% complete. Review and test before deploying to production.
      </p>
    </div>
  );
}
