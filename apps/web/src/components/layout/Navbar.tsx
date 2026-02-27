'use client';
import React from 'react';
import Link from 'next/link';
import { useTheme } from '@/lib/contexts/ThemeContext';
import { UserMenu } from './UserMenu';
import { NotificationPanel } from './NotificationPanel';
import { GlobalSearch } from './GlobalSearch';

export function Navbar() {
  const { theme, toggleTheme } = useTheme();

  return (
    <nav className="fixed top-0 left-0 right-0 h-16 bg-surface-card border-b border-surface-border z-50 px-6 flex items-center justify-between">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A6CF7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/>
          <circle cx="10" cy="9" r="1" fill="#4A6CF7"/>
          <circle cx="14" cy="9" r="1" fill="#4A6CF7"/>
          <circle cx="12" cy="12" r="1" fill="#4A6CF7"/>
          <path d="M10 9l2 3M14 9l-2 3"/>
        </svg>
        <span className="text-lg font-bold text-text-primary tracking-tight">
          AGENT <span className="text-text-primary">HUB</span>
        </span>
      </Link>

      {/* Search */}
      <GlobalSearch />

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Dark/Light toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-button hover:bg-surface-bg text-text-secondary transition-colors"
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          )}
        </button>

        {/* Notifications */}
        <NotificationPanel />

        {/* User Menu */}
        <UserMenu />
      </div>
    </nav>
  );
}
