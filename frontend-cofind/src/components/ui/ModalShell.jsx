import React, { useEffect, useId } from 'react';
import { cn } from '../../utils/cn';

export default function ModalShell({
  open,
  onClose,
  title,
  titleId: titleIdProp,
  description,
  children,
  className,
  panelClassName,
}) {
  const autoId = useId();
  const titleId = titleIdProp ?? `modal-title-${autoId}`;

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className={cn('fixed inset-0 z-50 flex items-center justify-center p-4', className)}
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 bg-cofind-ink/50"
        aria-label="Tutup dialog"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        className={cn(
          'relative z-10 w-full max-w-lg max-h-[min(90vh,48rem)] overflow-y-auto',
          'rounded-panel border border-cofind-rule bg-cofind-surface shadow-cofind-lg',
          panelClassName,
        )}
      >
        {title ? (
          <header className="border-b border-cofind-rule px-5 py-4">
            <h2 id={titleId} className="font-display text-lg font-bold text-cofind-ink">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-sm text-cofind-muted">{description}</p>
            ) : null}
          </header>
        ) : null}
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}