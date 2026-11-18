import React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../utils/cn';

export const COLLECTION_CTA_PRIMARY =
  'inline-flex items-center justify-center min-h-[2.75rem] rounded-control px-6 py-2.5 bg-cofind-primary text-cofind-on-primary font-medium shadow-cofind-sm transition-colors duration-200 hover:bg-cofind-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cofind-secondary';

export const COLLECTION_CTA_SECONDARY =
  'inline-flex items-center justify-center min-h-[2.75rem] rounded-control px-6 py-2.5 border border-cofind-rule bg-cofind-surface text-cofind-ink font-medium transition-colors duration-200 hover:bg-cofind-paper hover:text-cofind-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cofind-secondary';

export function CollectionPageLayout({ children, className }) {
  return (
    <div
      className={cn(
        'min-h-screen bg-cofind-background py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8',
        className,
      )}
    >
      <div className="mx-auto w-full max-w-cofind">{children}</div>
    </div>
  );
}

export function CollectionLoading({ message }) {
  return (
    <CollectionPageLayout>
      <p className="text-center text-lg text-cofind-muted">{message}</p>
    </CollectionPageLayout>
  );
}

export function CollectionLoginGate({ title, description }) {
  return (
    <CollectionPageLayout>
      <div className="mx-auto max-w-2xl py-12 text-center">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full border border-cofind-rule bg-cofind-paper text-cofind-secondary">
          <svg className="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>
        <h2 className="font-display text-2xl font-bold text-cofind-ink">{title}</h2>
        <p className="mt-4 mb-8 text-cofind-muted">{description}</p>
        <Link to="/login" className={COLLECTION_CTA_PRIMARY}>
          Masuk / Daftar
        </Link>
      </div>
    </CollectionPageLayout>
  );
}

export function CollectionEmptyState({
  icon,
  title,
  description,
  primaryTo,
  primaryLabel,
  secondaryTo,
  secondaryLabel,
}) {
  return (
    <CollectionPageLayout>
      <div className="py-8 text-center sm:py-12 md:py-16">
        {icon}
        <h1 className="mt-4 px-4 font-display text-2xl font-bold text-cofind-ink sm:mt-6 sm:text-3xl md:text-4xl">
          {title}
        </h1>
        <p className="mt-3 px-4 text-base text-cofind-muted sm:mt-4 sm:text-lg">{description}</p>
        <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
          <Link to={primaryTo} className={COLLECTION_CTA_PRIMARY}>
            {primaryLabel}
          </Link>
          {secondaryTo && secondaryLabel ? (
            <Link to={secondaryTo} className={COLLECTION_CTA_SECONDARY}>
              {secondaryLabel}
            </Link>
          ) : null}
        </div>
      </div>
    </CollectionPageLayout>
  );
}

export function CollectionPageHeader({ title, subtitle, icon }) {
  return (
    <div className="mb-8">
      <h1 className="mb-2 flex items-center gap-3 font-display text-2xl font-bold text-cofind-ink sm:text-3xl md:text-4xl">
        {icon}
        {title}
      </h1>
      {subtitle ? <p className="text-cofind-muted">{subtitle}</p> : null}
    </div>
  );
}