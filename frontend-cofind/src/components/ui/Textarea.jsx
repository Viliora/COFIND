import React from 'react';
import { cn } from '../../utils/cn';

export default function Textarea({ className, rows = 4, ...rest }) {
  return (
    <textarea
      rows={rows}
      className={cn(
        'w-full rounded-control border border-cofind-rule bg-cofind-surface px-3 py-2',
        'text-base text-cofind-ink placeholder:text-cofind-muted leading-relaxed',
        'focus:border-cofind-secondary focus:ring-2 focus:ring-cofind-secondary/25 focus:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...rest}
    />
  );
}