'use client';
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '@/lib/api';
import { NotificationItem } from '@/lib/types';

const agentColors: Record<string, string> = {
  'source-of-truth': 'bg-blue-500',
  'code-accelerator': 'bg-green-500',
  'data-triage': 'bg-purple-500',
  'Source of Truth': 'bg-blue-500',
  'Code Accelerator': 'bg-green-500',
  'Data Triage': 'bg-purple-500',
  'Knowledge Store': 'bg-yellow-500',
  'user': 'bg-gray-400',
};

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    if (isNaN(date.getTime())) return ts;
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  } catch {
    return ts;
  }
}

export function NotificationPanel() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const fetchNotifications = useCallback(async () => {
    try {
      const data = await getNotifications();
      if (data) setNotifications(data);
    } catch {
      // silently fail
    }
  }, []);

  // Fetch on mount and poll every 15 seconds
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarkAllRead = async () => {
    await markAllNotificationsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const handleMarkRead = async (id: string) => {
    await markNotificationRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => { setOpen(!open); if (!open) fetchNotifications(); }}
        className="p-2 rounded-button hover:bg-surface-bg text-text-secondary transition-colors relative"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-status-danger text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-surface-card border border-surface-border rounded-card shadow-lg z-50 max-h-96 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border">
            <h3 className="text-sm font-bold text-text-primary">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-brand-blue hover:text-brand-blue-hover transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="overflow-y-auto flex-1">
            {notifications.length === 0 ? (
              <div className="p-6 text-center text-sm text-text-muted">
                No notifications yet. Use an agent to get started.
              </div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleMarkRead(n.id)}
                  className={`w-full text-left px-4 py-3 border-b border-surface-border last:border-b-0 hover:bg-surface-bg transition-colors ${
                    !n.read ? 'bg-brand-blue/5' : ''
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${agentColors[n.agent] || 'bg-gray-400'}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-text-muted font-medium">
                        {n.agent} &middot; {formatTimestamp(n.timestamp)}
                      </p>
                      <p className="text-sm text-text-primary mt-0.5 leading-relaxed">{n.message}</p>
                    </div>
                    {!n.read && (
                      <div className="w-2 h-2 rounded-full bg-brand-blue flex-shrink-0 mt-1.5" />
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
