import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';

function truncateText(value, max = 140) {
  const text = String(value ?? '').trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function pillKey(item, index) {
  const id = item?.review_id ?? item?.reviewId;
  if (id != null && id !== '') return `review-${id}`;
  const quote = String(item?.quote ?? '').trim().toLowerCase().slice(0, 80);
  return quote ? `q-${quote}-${index}` : `src-${index}`;
}

function reviewTarget(placeId, item) {
  if (!placeId) return null;
  const reviewId = item?.review_id ?? item?.reviewId;
  if (reviewId == null || reviewId === '') {
    return { pathname: `/shop/${encodeURIComponent(placeId)}`, reviewId: null };
  }
  return {
    pathname: `/shop/${encodeURIComponent(placeId)}#review-${reviewId}`,
    reviewId: String(reviewId),
  };
}

const MAX_PANEL_QUOTES = 3;

const triggerClassName =
  'inline-flex max-w-full items-center gap-1 rounded-full border border-slate-200/90 bg-slate-50/80 px-2 py-0.5 text-[11px] font-normal leading-none text-slate-600 align-middle transition-colors hover:border-slate-300 hover:bg-slate-100 hover:text-slate-800 dark:border-zinc-600/70 dark:bg-zinc-800/50 dark:text-zinc-400 dark:hover:border-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-900';

function shopDetailPath(placeId) {
  if (!placeId) return null;
  return `/shop/${encodeURIComponent(placeId)}`;
}

function EvidenceReviewRow({ item, placeId, onClosePanel, onNavigate }) {
  const target = reviewTarget(placeId, item);
  const username = String(item?.username ?? '').trim();
  const metaParts = [
    username ? `@${username.replace(/^@+/, '')}` : null,
    item.rating != null && item.rating !== '' ? `★${item.rating}` : null,
    item.pill_label ? String(item.pill_label) : null,
  ].filter(Boolean);

  const body = (
    <>
      <p className="text-sm italic leading-snug text-gray-800 dark:text-gray-100">
        &ldquo;{truncateText(item.quote, 220)}&rdquo;
      </p>
      {metaParts.length > 0 ? (
        <p className="mt-1.5 text-[11px] text-gray-500 dark:text-zinc-400">{metaParts.join(' · ')}</p>
      ) : null}
      {target ? (
        <p className="mt-1 text-[10px] font-medium text-indigo-600/90 dark:text-indigo-400/90">
          Buka ulasan di halaman toko →
        </p>
      ) : null}
    </>
  );

  const rowClass =
    'block rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5 text-left transition-colors dark:border-zinc-700/80 dark:bg-zinc-900/40';

  if (!target) {
    return <div className={rowClass}>{body}</div>;
  }

  const handleClick = (e) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    onClosePanel?.();
    onNavigate?.();
  };

  return (
    <Link
      to={target.pathname}
      state={target.reviewId ? { focusReviewId: target.reviewId } : undefined}
      onClick={handleClick}
      className={`${rowClass} w-full cursor-pointer no-underline hover:border-indigo-200 hover:bg-indigo-50/50 dark:hover:border-indigo-800/50 dark:hover:bg-indigo-950/20`}
    >
      {body}
    </Link>
  );
}

function computePanelPosition(triggerRect) {
  const margin = 12;
  const panelWidth = Math.min(320, window.innerWidth - margin * 2);
  let left = triggerRect.left;
  if (left + panelWidth > window.innerWidth - margin) {
    left = window.innerWidth - margin - panelWidth;
  }
  if (left < margin) left = margin;

  const spaceBelow = window.innerHeight - triggerRect.bottom - margin;
  const preferBelow = spaceBelow >= 120 || spaceBelow >= triggerRect.top;
  if (preferBelow) {
    return { top: triggerRect.bottom + 6, left, width: panelWidth, placement: 'below' };
  }
  return {
    bottom: window.innerHeight - triggerRect.top + 6,
    left,
    width: panelWidth,
    placement: 'above',
  };
}

/**
 * Satu pill ringkas; klik membuka bubble berisi kutipan ulasan relevan.
 * Tiap ulasan di bubble dapat diklik menuju review di halaman coffee shop.
 */
export default function RecommendationReviewSourcePills({
  items = [],
  placeId = null,
  onNavigate,
  className = '',
  showLabel = false,
}) {
  const list = Array.isArray(items) ? items.filter((item) => item?.quote || item?.username) : [];
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState(null);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const panelId = useId();

  const closePanel = useCallback(() => setOpen(false), []);

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pos = computePanelPosition(rect);
    setPanelStyle({
      top: pos.top,
      bottom: pos.bottom,
      left: pos.left,
      width: pos.width,
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return undefined;
    updatePosition();
    const onScrollOrResize = () => updatePosition();
    window.addEventListener('resize', onScrollOrResize);
    window.addEventListener('scroll', onScrollOrResize, true);
    return () => {
      window.removeEventListener('resize', onScrollOrResize);
      window.removeEventListener('scroll', onScrollOrResize, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (e) => {
      if (e.key === 'Escape') closePanel();
    };
    const onPointerDown = (e) => {
      const t = e.target;
      if (triggerRef.current?.contains(t) || panelRef.current?.contains(t)) return;
      closePanel();
    };

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onPointerDown);
    };
  }, [open, closePanel]);

  if (!list.length) return null;

  const totalCount = list.length;
  const hasMoreThanMax = totalCount > MAX_PANEL_QUOTES;
  const countLabel =
    totalCount === 1
      ? '1 bukti ulasan'
      : hasMoreThanMax
        ? '3 and more bukti ulasan'
        : `${totalCount} bukti ulasan`;
  const panelItems = hasMoreThanMax ? list.slice(0, MAX_PANEL_QUOTES) : list;
  const detailPath = shopDetailPath(placeId);

  const bubble =
    open && panelStyle
      ? createPortal(
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-labelledby={`${panelId}-title`}
            className="fixed z-[120] flex h-[min(17.5rem,42vh)] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-3 shadow-lg ring-1 ring-black/5 dark:border-zinc-700 dark:bg-zinc-900 dark:ring-white/10"
            style={panelStyle}
          >
            <p
              id={`${panelId}-title`}
              className="mb-2 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-gray-500 dark:text-zinc-400"
            >
              Bukti ulasan relevan
            </p>
            <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-y-contain pr-0.5 [-webkit-overflow-scrolling:touch]">
              {panelItems.map((item, index) => (
                <li key={pillKey(item, index)}>
                  <EvidenceReviewRow
                    item={item}
                    placeId={placeId}
                    onClosePanel={closePanel}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
            {hasMoreThanMax && detailPath ? (
              <div className="mt-2 shrink-0 border-t border-slate-100 pt-2 dark:border-zinc-700/80">
                <Link
                  to={detailPath}
                  onClick={(e) => {
                    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                    closePanel();
                    onNavigate?.();
                  }}
                  className="block text-center text-[11px] font-semibold text-indigo-600 no-underline hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
                >
                  See more
                </Link>
              </div>
            ) : null}
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <span
        className={`inline-flex items-center align-middle ${className}`.trim()}
      >
        {showLabel ? (
          <span className="w-full shrink-0 text-[10px] font-medium uppercase tracking-wide text-gray-400 dark:text-zinc-500 sm:w-auto">
            Sumber ulasan
          </span>
        ) : null}
        <button
          ref={triggerRef}
          type="button"
          aria-expanded={open}
          aria-controls={open ? panelId : undefined}
          onClick={() => setOpen((v) => !v)}
          className={triggerClassName}
        >
          <span aria-hidden className="opacity-70">
            💬
          </span>
          <span>{countLabel}</span>
        </button>
      </span>
      {bubble}
    </>
  );
}
