'use client';
import React, { useEffect, useState } from 'react';
import { getActivity } from '@/lib/api';
import { ActivityItem } from '@/lib/types';

const agentColors: Record<string, string> = {
  'source-of-truth': 'bg-blue-500',
  'code-accelerator': 'bg-green-500',
  'data-triage': 'bg-purple-500',
  'Source of Truth': 'bg-blue-500',
  'Code Accelerator': 'bg-green-500',
  'Data Triage': 'bg-purple-500',
  'user': 'bg-gray-400',
};

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    if (isNaN(date.getTime())) return ts;
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  } catch {
    return ts;
  }
}

export function RecentActivity() {
  const [activities, setActivities] = useState<ActivityItem[]>([]);

  useEffect(() => {
    const fetchActivities = () => {
      getActivity()
        .then((data) => {
          if (data) setActivities(data);
        })
        .catch(() => {});
    };

    fetchActivities();
    const interval = setInterval(fetchActivities, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h2 className="text-sm font-bold text-text-primary tracking-wide uppercase mb-4">
        Recent Activity
      </h2>
      {activities.length === 0 ? (
        <div className="p-6 bg-surface-card border border-surface-border rounded-card text-center">
          <p className="text-sm text-text-muted">
            No activity yet. Start using agents to see your history here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {activities.slice(0, 4).map((item) => (
            <div key={item.id} className="flex items-start gap-3 p-4 bg-surface-card border border-surface-border rounded-card">
              <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${agentColors[item.agent] || 'bg-gray-400'}`} />
              <div className="min-w-0">
                <span className="text-xs text-text-muted font-medium">{formatTimestamp(item.timestamp)}:</span>
                <p className="text-sm text-text-primary mt-0.5 leading-relaxed">{item.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
