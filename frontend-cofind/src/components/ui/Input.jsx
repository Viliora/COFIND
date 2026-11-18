import React from 'react';
import { cn } from '../../utils/cn';

export default function Input({ className, ...rest }) {
  return (
    <input
      className={cn(
        'w-full min-h-[2.75rem] rounded-control border border-cofind-rule bg-cofind-surface px-3 py-2',
        'text-base text-cofind-ink placeholder:text-cofind-muted',
        'focus:border-cofind-secondary focus:ring-2 focus:ring-cofind-secondary/25 focus:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...rest}
    />
  );
}