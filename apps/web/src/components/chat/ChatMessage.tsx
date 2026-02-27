'use client';
import React from 'react';

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  structuredData?: Record<string, unknown> | null;
  dataType?: string | null;
  timestamp: Date;
}

interface ChatMessageProps {
  message: ChatMessageData;
  renderStructuredData?: (data: Record<string, unknown>, dataType: string) => React.ReactNode;
}

export function ChatMessage({ message, renderStructuredData }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`flex gap-3 max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${
          isUser ? 'bg-brand-blue' : 'bg-status-success'
        }`}>
          {isUser ? 'U' : 'AI'}
        </div>

        {/* Message bubble */}
        <div className={`rounded-card px-4 py-3 ${
          isUser
            ? 'bg-brand-blue text-white'
            : 'bg-surface-card border border-surface-border text-text-primary'
        }`}>
          {/* Text content */}
          {message.content && (
            <div className={`text-sm leading-relaxed whitespace-pre-wrap ${
              isUser ? 'text-white' : 'text-text-primary'
            }`}>
              {message.content}
            </div>
          )}

          {/* Structured data */}
          {message.structuredData && message.dataType && renderStructuredData && (
            <div className="mt-3">
              {renderStructuredData(message.structuredData, message.dataType)}
            </div>
          )}

          {/* Timestamp */}
          <div className={`text-[10px] mt-2 ${
            isUser ? 'text-blue-200' : 'text-text-muted'
          }`}>
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    </div>
  );
}
