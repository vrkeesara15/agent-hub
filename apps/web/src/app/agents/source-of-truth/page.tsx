'use client';
import React, { useState, useCallback, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { SearchBar } from '@/components/source-of-truth/SearchBar';
import { RecommendedTable } from '@/components/source-of-truth/RecommendedTable';
import { OtherTables } from '@/components/source-of-truth/OtherTables';
import { ConfidenceBadge } from '@/components/source-of-truth/ConfidenceBadge';
import { searchTables } from '@/lib/api';
import { SearchResponse } from '@/lib/types';

function SourceOfTruthContent() {
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const searchParams = useSearchParams();

  const handleSearch = useCallback(async (query: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await searchTables(query);
      setResult(data);
    } catch (err) {
      setError('Failed to search. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-search from URL query param (from global search)
  useEffect(() => {
    const q = searchParams.get('q');
    if (q) {
      handleSearch(q);
    }
  }, [searchParams, handleSearch]);

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary uppercase tracking-wide">Find the Right Table</h1>
        </div>
        <div className="flex items-center gap-4">
          <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'Find the Right Table' }]} />
          <button className="w-8 h-8 rounded-full border border-surface-border flex items-center justify-center text-text-muted hover:bg-gray-50 dark:hover:bg-gray-800">
            <span className="text-sm font-medium">?</span>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-8">
        <SearchBar onSearch={handleSearch} loading={loading} />
      </div>

      {/* Loading shimmer */}
      {loading && (
        <div className="space-y-4 max-w-3xl mx-auto">
          <div className="h-8 shimmer rounded-md w-48" />
          <div className="h-48 shimmer rounded-card" />
          <div className="h-24 shimmer rounded-card" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="max-w-3xl mx-auto p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-card text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="max-w-3xl mx-auto">
          <RecommendedTable table={result.recommended} />
          <OtherTables tables={result.alternatives} />
          <ConfidenceBadge level={result.confidence} />
        </div>
      )}
    </div>
  );
}

export default function SourceOfTruthPage() {
  return (
    <Suspense fallback={
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="space-y-4">
          <div className="h-8 shimmer rounded-md w-48" />
          <div className="h-14 shimmer rounded-card max-w-3xl mx-auto" />
        </div>
      </div>
    }>
      <SourceOfTruthContent />
    </Suspense>
  );
}
