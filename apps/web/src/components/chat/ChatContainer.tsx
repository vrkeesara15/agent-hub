'use client';
import React, { useRef, useEffect } from 'react';
import { ChatMessage, ChatMessageData } from './ChatMessage';
import { ChatInput } from './ChatInput';

interface ChatContainerProps {
  messages: ChatMessageData[];
  onSend: (message: string) => void;
  onFileAttach?: (content: string, filename: string) => void;
  loading?: boolean;
  placeholder?: string;
  showFileAttach?: boolean;
  renderStructuredData?: (data: Record<string, unknown>, dataType: string) => React.ReactNode;
  emptyStateMessage?: string;
  emptyStateHint?: string;
}

export function ChatContainer({
  messages,
  onSend,
  onFileAttach,
  loading = false,
  placeholder,
  showFileAttach = false,
  renderStructuredData,
  emptyStateMessage = 'Start a conversation',
  emptyStateHint = 'Type your question below to get started.',
}: ChatContainerProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] bg-surface-bg rounded-card border border-surface-border overflow-hidden">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full bg-brand-blue/10 flex items-center justify-center mb-4">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#4A6CF7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-text-primary mb-2">{emptyStateMessage}</h3>
            <p className="text-sm text-text-secondary max-w-md">{emptyStateHint}</p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                renderStructuredData={renderStructuredData}
              />
            ))}

            {/* Loading indicator */}
            {loading && (
              <div className="flex justify-start mb-4">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-status-success flex items-center justify-center text-white text-xs font-bold">
                    AI
                  </div>
                  <div className="bg-surface-card border border-surface-border rounded-card px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-sm text-text-muted">Thinking...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input area */}
      <ChatInput
        onSend={onSend}
        onFileAttach={onFileAttach}
        loading={loading}
        placeholder={placeholder}
        showFileAttach={showFileAttach}
      />
    </div>
  );
}
