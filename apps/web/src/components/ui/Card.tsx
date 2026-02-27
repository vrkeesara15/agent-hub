import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}

export function Card({ children, className = '', padding = true }: CardProps) {
  return (
    <div className={`bg-surface-card border border-surface-border rounded-card shadow-card ${padding ? 'p-6' : ''} ${className}`}>
      {children}
    </div>
  );
}
