import React from 'react';
import { cn } from '../lib/cn';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export default function Card({ className, children, ...props }: CardProps) {
  return (
    <div className={cn('glass-surface rounded-lg p-6', className)} {...props}>
      {children}
    </div>
  );
}
