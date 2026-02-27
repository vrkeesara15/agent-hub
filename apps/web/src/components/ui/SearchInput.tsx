'use client';
import React, { useState } from 'react';

interface SearchInputProps {
  placeholder?: string;
  onSearch: (query: string) => void;
  loading?: boolean;
  size?: 'default' | 'large';
}

export function SearchInput({ placeholder = 'Search...', onSearch, loading = false, size = 'default' }: SearchInputProps) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim()) onSearch(value.trim());
  };

  const sizeClasses = size === 'large'
    ? 'h-14 text-base pl-5 pr-28'
    : 'h-10 text-sm pl-4 pr-20';

  const buttonClasses = size === 'large'
    ? 'px-6 py-2 text-base'
    : 'px-4 py-1.5 text-sm';

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className={`w-full ${sizeClasses} bg-surface-card border border-surface-border rounded-card text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent`}
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        className={`absolute right-2 top-1/2 -translate-y-1/2 ${buttonClasses} bg-status-success text-white rounded-button font-medium hover:bg-green-600 transition-colors disabled:opacity-50`}
      >
        {loading ? (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        ) : 'Search'}
      </button>
    </form>
  );
}
