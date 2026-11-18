import React from 'react';
import { cn } from '../../utils/cn';

const TONES = {
  neutral: 'bg-cofind-paper text-cofind-ink border-cofind-rule',
  primary: 'bg-cofind-primary text-cofind-on-primary border-cofind-primary',
  secondary: 'bg-cofind-secondary text-cofind-on-secondary border-cofind-secondary',
  positive: 'bg-emerald-800 text-white border-emerald-900',
  negative: 'bg-red-800 text-white border-red-900',
};

export default function Badge({ tone = 'neutral', className, children, ...rest }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-control border px-2 py-0.5 text-xs font-medium',
        TONES[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}