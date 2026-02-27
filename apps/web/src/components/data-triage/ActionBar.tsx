import React from 'react';
import { Button } from '@/components/ui/Button';

interface ActionBarProps {
  onExport?: () => void;
  onSetAlerts?: () => void;
  onScanAgain?: () => void;
}

export function ActionBar({ onExport, onSetAlerts, onScanAgain }: ActionBarProps) {
  return (
    <div className="mt-6 flex items-center gap-3 pt-6 border-t border-surface-border">
      <Button variant="outline" onClick={onExport}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        Export Report
      </Button>
      <Button variant="outline" onClick={onSetAlerts}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 01-3.46 0"/>
        </svg>
        Set Up Alerts
      </Button>
      <Button variant="primary" onClick={onScanAgain}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
        </svg>
        Scan Again
      </Button>
    </div>
  );
}
