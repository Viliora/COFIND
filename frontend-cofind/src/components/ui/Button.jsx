import React from 'react';
import { cn } from '../../utils/cn';

const VARIANTS = {
  primary:
    'bg-cofind-primary text-cofind-on-primary hover:bg-cofind-primary-hover border border-transparent shadow-cofind-sm',
  secondary:
    'bg-cofind-surface text-cofind-ink border border-cofind-rule hover:bg-cofind-paper shadow-cofind-sm',
  ghost: 'bg-transparent text-cofind-ink border border-transparent hover:bg-cofind-paper',
  danger: 'bg-red-700 text-white border border-transparent hover:bg-red-800 shadow-cofind-sm',
  link: 'bg-transparent text-cofind-secondary underline-offset-4 hover:underline border-0 p-0 min-h-0',
};

const SIZES = {
  sm: 'min-h-[2.25rem] px-3 py-1.5 text-sm',
  md: 'min-h-[2.75rem] px-4 py-2 text-sm font-medium',
  lg: 'min-h-[3rem] px-5 py-2.5 text-base font-medium',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  type = 'button',
  className,
  disabled,
  children,
  ...rest
}) {
  const isLink = variant === 'link';

  return (
    <button
      type={type}
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center rounded-control font-sans transition-colors duration-200',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cofind-secondary',
        'disabled:cursor-not-allowed disabled:opacity-50',
        !isLink && VARIANTS[variant],
        !isLink && SIZES[size],
        isLink && VARIANTS.link,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}