'use client';
import React from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/Card';
import { StatusDot } from '@/components/ui/StatusDot';
import { Button } from '@/components/ui/Button';

interface AgentCardProps {
  title: string;
  href: string;
  icon: React.ReactNode;
  status: 'active' | 'warning' | 'error' | 'inactive';
  children: React.ReactNode;
}

export function AgentCard({ title, href, icon, status, children }: AgentCardProps) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950 flex items-center justify-center flex-shrink-0">
          {icon}
        </div>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <h3 className="text-sm font-bold text-text-primary tracking-wide uppercase">{title}</h3>
          <StatusDot status={status} />
        </div>
      </div>
      <div className="flex-1 mb-4">
        {children}
      </div>
      <Link href={href}>
        <Button fullWidth variant="primary" size="lg">Open Agent</Button>
      </Link>
    </Card>
  );
}
