import React from 'react';
import { cn } from '../lib/cn';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

export default function Textarea({ className, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        'w-full px-4 py-3 border border-border rounded-lg bg-bg text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent resize-none',
        className
      )}
      {...props}
    />
  );
}
