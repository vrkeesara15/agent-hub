'use client';
import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';

interface SearchItem {
  label: string;
  description: string;
  href: string;
  category: 'agent' | 'page' | 'action';
  keywords: string[];
}

const searchItems: SearchItem[] = [
  {
    label: 'Object Iq',
    description: 'Smart object discovery across data sources',
    href: '/agents/source-of-truth',
    category: 'agent',
    keywords: ['table', 'search', 'find', 'sql', 'bigquery', 'data', 'source', 'truth', 'dimension', 'customer', 'object', 'iq', 'discovery'],
  },
  {
    label: 'Accelerated Cloud Migration',
    description: 'Convert legacy SQL to modern cloud code',
    href: '/agents/code-accelerator',
    category: 'agent',
    keywords: ['convert', 'migrate', 'teradata', 'airflow', 'sql', 'code', 'tableau', 'looker', 'bigquery', 'legacy', 'accelerator', 'launchpad'],
  },
  {
    label: 'Data Health & Observability',
    description: 'Scan pipelines for issues and get fixes',
    href: '/agents/data-triage',
    category: 'agent',
    keywords: ['scan', 'triage', 'monitor', 'health', 'alert', 'fix', 'pipeline', 'issue', 'deprecated', 'datalens', 'observability'],
  },
  {
    label: 'Informatica Migration',
    description: 'Convert Informatica PowerCenter XML to GCP',
    href: '/agents/informatica-migration',
    category: 'agent',
    keywords: ['informatica', 'xml', 'powerCenter', 'migration', 'bigquery', 'airflow', 'dag', 'scd', 'merge', 'etl'],
  },
  {
    label: 'Admin & Settings',
    description: 'API configuration and knowledge base',
    href: '/admin',
    category: 'page',
    keywords: ['settings', 'config', 'admin', 'api', 'key', 'knowledge', 'upload'],
  },
  {
    label: 'Dashboard',
    description: 'Home dashboard with agent overview',
    href: '/',
    category: 'page',
    keywords: ['home', 'dashboard', 'overview', 'activity'],
  },
];

const categoryLabels: Record<string, string> = {
  agent: 'Agent',
  page: 'Page',
  action: 'Action',
};

const categoryIcons: Record<string, React.ReactNode> = {
  agent: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/>
    </svg>
  ),
  page: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
    </svg>
  ),
  action: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
    </svg>
  ),
};

export function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const allResults = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();

    const matched = searchItems.filter((item) =>
      item.label.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      item.keywords.some((kw) => kw.includes(q))
    );

    // Always add a "Search Object IQ" action if query >= 2 chars
    if (query.trim().length >= 2) {
      matched.push({
        label: `Search "${query.trim()}" in Object Iq`,
        description: 'Find tables matching this query',
        href: `/agents/source-of-truth?q=${encodeURIComponent(query.trim())}`,
        category: 'action',
        keywords: [],
      });
    }

    return matched;
  }, [query]);

  const showDropdown = focused && query.trim().length > 0;

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown || allResults.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, allResults.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && allResults[selectedIndex]) {
      e.preventDefault();
      router.push(allResults[selectedIndex].href);
      setQuery('');
      setFocused(false);
    } else if (e.key === 'Escape') {
      setFocused(false);
    }
  };

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setFocused(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset selected index when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  return (
    <div className="flex-1 max-w-xl mx-8 relative" ref={ref}>
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.3-4.3"/>
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search agents, metrics, workflows..."
          className="w-full h-10 pl-10 pr-4 bg-surface-bg border border-surface-border rounded-button text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent"
        />
      </div>

      {showDropdown && allResults.length > 0 && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-surface-card border border-surface-border rounded-card shadow-lg z-50 overflow-hidden py-1">
          {allResults.map((item, index) => (
            <button
              key={item.href + item.label}
              onClick={() => {
                router.push(item.href);
                setQuery('');
                setFocused(false);
              }}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`w-full text-left flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                index === selectedIndex
                  ? 'bg-brand-blue/10'
                  : 'hover:bg-surface-bg'
              }`}
            >
              <div className="w-8 h-8 rounded-lg bg-surface-bg flex items-center justify-center flex-shrink-0 text-text-secondary">
                {categoryIcons[item.category]}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-primary truncate">{item.label}</p>
                <p className="text-xs text-text-muted truncate">{item.description}</p>
              </div>
              <span className="text-[10px] tracking-wider text-text-muted font-medium flex-shrink-0">
                {categoryLabels[item.category]}
              </span>
            </button>
          ))}
        </div>
      )}

      {showDropdown && allResults.length === 0 && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-surface-card border border-surface-border rounded-card shadow-lg z-50 p-4 text-center text-sm text-text-muted">
          No results found
        </div>
      )}
    </div>
  );
}
