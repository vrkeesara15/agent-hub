'use client';
import React, { useState } from 'react';
import { DashboardView } from '@/components/home/DashboardView';
import { WelcomeView } from '@/components/home/WelcomeView';

export default function HomePage() {
  const [view, setView] = useState<'dashboard' | 'welcome'>('dashboard');

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* View Toggle */}
      <div className="flex justify-end mb-6">
        <div className="flex items-center bg-surface-card border border-surface-border rounded-button overflow-hidden">
          <button
            onClick={() => setView('dashboard')}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              view === 'dashboard'
                ? 'bg-brand-blue text-white'
                : 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="inline mr-1.5 -mt-0.5">
              <rect x="3" y="3" width="7" height="7"/>
              <rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/>
            </svg>
            Dashboard
          </button>
          <button
            onClick={() => setView('welcome')}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              view === 'welcome'
                ? 'bg-brand-blue text-white'
                : 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="inline mr-1.5 -mt-0.5">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            Welcome
          </button>
        </div>
      </div>

      {view === 'dashboard' ? <DashboardView /> : <WelcomeView />}
    </div>
  );
}
