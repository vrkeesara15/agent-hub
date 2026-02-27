'use client';
import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  children: React.ReactNode;
}

export function Button({ variant = 'primary', size = 'md', fullWidth = false, children, className = '', ...props }: ButtonProps) {
  const base = 'inline-flex items-center justify-center font-medium transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-brand-blue text-white hover:bg-brand-blue-hover',
    outline: 'border border-surface-border text-text-primary hover:bg-gray-50 dark:hover:bg-gray-800',
    ghost: 'text-text-secondary hover:bg-gray-100 dark:hover:bg-gray-800',
  };

  const sizes = {
    sm: 'text-sm px-3 h-8 rounded-md',
    md: 'text-sm px-4 h-10 rounded-button',
    lg: 'text-base px-6 h-11 rounded-button',
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${fullWidth ? 'w-full' : ''} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
