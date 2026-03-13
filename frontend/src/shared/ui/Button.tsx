import React from 'react';
import { cn } from '../lib/cn';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const base = 'inline-flex items-center justify-center rounded-lg transition-colors duration-fast focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2';
  const variants = {
    primary: 'bg-brand text-white hover:bg-brand-strong disabled:opacity-50 disabled:cursor-not-allowed',
    secondary: 'bg-surface border border-border text-text hover:bg-surface-2 disabled:opacity-50 disabled:cursor-not-allowed',
    danger: 'bg-ai-danger text-white hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed',
  } as const;
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3',
  } as const;

  return (
    <button
      className={cn(base, variants[variant], sizes[size], fullWidth && 'w-full', className)}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
