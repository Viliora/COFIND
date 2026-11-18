import React from 'react';
import { cn } from '../../utils/cn';

/**
 * Single-layer surface — no card-in-card nesting in new layouts.
 */
export default function Card({ as: Component = 'div', className, children, ...rest }) {
  return (
    <Component
      className={cn(
        'rounded-panel border border-cofind-rule bg-cofind-surface text-cofind-ink shadow-cofind-sm',
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  );
}