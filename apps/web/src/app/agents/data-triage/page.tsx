'use client';
import React, { useState, useCallback } from 'react';
import Link from 'next/link';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { ChatMessageData } from '@/components/chat/ChatMessage';
import { renderStructuredData } from '@/components/chat/StructuredDataRenderer';
import { chatDataTriage } from '@/lib/api';

export default function DataTriagePage() {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<{ role: string; content: string }[]>([]);

  const handleSend = useCallback(async (message: string) => {
    const userMsg: ChatMessageData = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    const newHistory = [...history, { role: 'user', content: message }];
    setLoading(true);

    try {
      const response = await chatDataTriage(message, history);

      const assistantMsg: ChatMessageData = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response_text,
        structuredData: response.structured_data,
        dataType: response.data_type,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMsg]);
      setHistory([...newHistory, { role: 'assistant', content: response.response_text }]);
    } catch {
      const errorMsg: ChatMessageData = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error connecting to the backend. Please check that the backend is running and try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }, [history]);

  const handleFileAttach = useCallback(async (content: string, filename: string) => {
    const userMsg: ChatMessageData = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: `[Attached file: ${filename}]\n\nPlease scan this SQL file for table health issues.`,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    setLoading(true);

    try {
      const response = await chatDataTriage(content, history);

      const assistantMsg: ChatMessageData = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response_text,
        structuredData: response.structured_data,
        dataType: response.data_type,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMsg]);
      setHistory(prev => [
        ...prev,
        { role: 'user', content: `Scan file ${filename}` },
        { role: 'assistant', content: response.response_text },
      ]);
    } catch {
      const errorMsg: ChatMessageData = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error scanning the file. Please check the backend and try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }, [history]);

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand-blue transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back
          </Link>
          <span className="text-surface-border">|</span>
          <h1 className="text-lg font-bold text-text-primary tracking-wide">DataLens</h1>
        </div>
        <Breadcrumb items={[{ label: 'Home', href: '/' }, { label: 'DataLens' }]} />
      </div>

      {/* Chat */}
      <ChatContainer
        messages={messages}
        onSend={handleSend}
        onFileAttach={handleFileAttach}
        loading={loading}
        placeholder="Ask about table health... e.g., 'Check health of dim_customer' or paste SQL code"
        showFileAttach
        renderStructuredData={renderStructuredData}
        emptyStateMessage="DataLens"
        emptyStateHint="Ask me to check the health of any table, paste SQL code to scan for issues, or attach a .sql file. For example: 'What is the status of analytics.fact_sales?' or 'Check health of dim_customer'"
      />
    </div>
  );
}
