'use client';
import React, { useState, useRef } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  onFileAttach?: (content: string, filename: string) => void;
  loading?: boolean;
  placeholder?: string;
  showFileAttach?: boolean;
}

export function ChatInput({
  onSend,
  onFileAttach,
  loading = false,
  placeholder = 'Type your message...',
  showFileAttach = false,
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !loading) {
      onSend(value.trim());
      setValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onFileAttach) return;
    const reader = new FileReader();
    reader.onload = () => {
      onFileAttach(reader.result as string, file.name);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-surface-border bg-surface-card p-4">
      <div className="flex items-end gap-2">
        {showFileAttach && (
          <>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex-shrink-0 p-2 rounded-button text-text-muted hover:text-text-secondary hover:bg-surface-bg transition-colors"
              title="Attach SQL file"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".sql,.txt,.csv"
              onChange={handleFileChange}
              className="hidden"
            />
          </>
        )}
        <div className="flex-1 relative">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={loading}
            className="w-full resize-none rounded-card border border-surface-border bg-surface-bg px-4 py-3 pr-12 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent disabled:opacity-50 min-h-[44px] max-h-[120px]"
            style={{ height: 'auto', overflow: 'hidden' }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = 'auto';
              target.style.height = Math.min(target.scrollHeight, 120) + 'px';
              target.style.overflow = target.scrollHeight > 120 ? 'auto' : 'hidden';
            }}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="flex-shrink-0 p-3 rounded-card bg-brand-blue text-white hover:bg-brand-blue-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}
