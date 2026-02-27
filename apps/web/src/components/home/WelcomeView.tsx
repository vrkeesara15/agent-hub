'use client';
import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';

const cards = [
  {
    tag: 'FIND THE RIGHT TABLE',
    bgClass: 'bg-blue-50 dark:bg-blue-950',
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="6"/>
        <circle cx="12" cy="12" r="2" fill="#EF4444"/>
      </svg>
    ),
    heading: 'Which table should I use?',
    subtext: 'Search across all your data sources',
    href: '/agents/source-of-truth',
    pills: null,
  },
  {
    tag: 'CONVERT YOUR CODE',
    bgClass: 'bg-green-50 dark:bg-green-950',
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="1.5">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="#FDE68A"/>
      </svg>
    ),
    heading: 'Migrate to Google Cloud',
    subtext: null,
    href: '/agents/code-accelerator',
    pills: ['Tableau\u2192Looker', 'SQL\u2192Airflow', 'Cron\u2192GCP'],
  },
  {
    tag: 'CHECK DATA HEALTH',
    bgClass: 'bg-purple-50 dark:bg-purple-950',
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/>
        <path d="m21 21-4.3-4.3"/>
      </svg>
    ),
    heading: 'Scan code for table issues',
    subtext: 'Find problems before they break',
    href: '/agents/data-triage',
    pills: null,
  },
];

const recentItems = [
  {
    color: 'bg-blue-500',
    text: "You converted 'Sales_Data_Migrate.sql' from SQL to Airflow.",
    time: '15 mins ago',
  },
  {
    color: 'bg-green-500',
    text: "You scheduled 'Daily_Performance_Cron' for migration to GCP.",
    time: '2 hours ago',
  },
  {
    color: 'bg-status-success',
    text: "You completed 'Data_Health_Scan_Q1' and resolved 3 issues.",
    time: 'Yesterday at 4:30 PM',
    isCheck: true,
  },
];

export function WelcomeView() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-text-primary">
        Welcome back! What would you like to do today?
      </h1>

      {/* Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {cards.map((card) => (
          <div key={card.tag} className={`${card.bgClass} rounded-card p-6 border border-transparent`}>
            <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-text-secondary bg-white/70 dark:bg-black/30 px-2 py-1 rounded mb-4">
              {card.tag}
            </span>
            <div className="mb-3">{card.icon}</div>
            <h3 className="text-lg font-bold text-text-primary mb-1">{card.heading}</h3>
            {card.subtext && (
              <p className="text-sm text-text-secondary mb-4">{card.subtext}</p>
            )}
            {card.pills && (
              <div className="flex flex-wrap gap-1.5 mb-4">
                {card.pills.map((pill) => (
                  <span key={pill} className="text-xs px-2 py-0.5 bg-white/80 dark:bg-black/30 rounded-full text-text-secondary border border-white dark:border-gray-700">
                    {pill}
                  </span>
                ))}
              </div>
            )}
            <Link href={card.href}>
              <Button variant="primary" size="md">Get Started</Button>
            </Link>
          </div>
        ))}
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="text-sm font-bold text-text-primary tracking-wide uppercase mb-4">
          Recent Activity
        </h2>
        <div className="space-y-3">
          {recentItems.map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-3">
              {item.isCheck ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="mt-0.5 flex-shrink-0">
                  <circle cx="12" cy="12" r="10" fill="#22C55E"/>
                  <path d="M8 12l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : (
                <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${item.color}`} />
              )}
              <div>
                <span className="text-sm text-text-primary">{item.text}</span>
                <span className="text-xs text-text-muted ml-2">- {item.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
