import React from 'react';

interface StatusDotProps {
  status: 'active' | 'warning' | 'error' | 'inactive';
  size?: 'sm' | 'md';
}

export function StatusDot({ status, size = 'sm' }: StatusDotProps) {
  const colors = {
    active: 'bg-status-success',
    warning: 'bg-status-warning',
    error: 'bg-status-danger',
    inactive: 'bg-gray-400',
  };
  const sizes = { sm: 'w-2 h-2', md: 'w-3 h-3' };

  return (
    <span className={`inline-block rounded-full ${colors[status]} ${sizes[size]}`} />
  );
}
