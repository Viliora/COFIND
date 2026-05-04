// src/components/RecommendationModal.jsx
import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { CONTEXT_PILL_OPTIONS } from '../constants/reviewPills';

function normalizeMatchText(value) {
    return String(value ?? '').trim().toLowerCase();
}

function pillLabelsFromValues(values) {
    const map = Object.fromEntries(CONTEXT_PILL_OPTIONS.map((p) => [p.value, p.label]));
    return (Array.isArray(values) ? values : []).map((v) => map[v] || v).filter(Boolean);
}

function formatQuoteReason(value) {
    const text = String(value ?? '').trim();
    if (!text) return '';
    return text
        .replace(/^review menyebut:\s*/i, '')
        .replace(/^komentar menyebut:\s*/i, '')
        .replace(/"/g, '');
}

function getShopDisplayName(rec, shop) {
    return String(rec?.name || shop?.name || 'Coffee shop').trim();
}

function quoteDedupeKey(quote) {
    return String(quote ?? '').trim().toLowerCase().slice(0, 160);
}

/** Pratinjau kutipan di kartu (maks. panjang karakter); teks lengkap di `title` hover. */
const MODAL_QUOTE_PREVIEW_MAX = 50;

function truncateQuotePreview(text, maxLen = MODAL_QUOTE_PREVIEW_MAX) {
    const s = String(text ?? '').trim();
    if (s.length <= maxLen) {
        return { preview: s, truncated: false };
    }
    const ellipsis = '…';
    const budget = Math.max(1, maxLen - ellipsis.length);
    let cut = s.slice(0, budget);
    const lastSpace = cut.lastIndexOf(' ');
    if (lastSpace > Math.floor(budget * 0.35)) {
        cut = cut.slice(0, lastSpace);
    }
    return { preview: `${cut}${ellipsis}`, truncated: true };
}

/** Kata/frasa relevan untuk baris meta: utuh, tidak dipotong (reason atau matched_terms). */
function fullRelevantPhrasesText(item) {
    const terms = item?.matched_terms;
    if (Array.isArray(terms) && terms.length > 0) {
        return terms
            .map((t) => String(t ?? '').trim())
            .filter(Boolean)
            .join(', ');
    }
    return formatQuoteReason(item?.reason);
}

/**
 * Bukti selaras preferensi: review_quotes (pill / keyword / llm_preference),
 * lalu positive_review_quotes, lalu search_keyword_matches — tanpa duplikat.
 * Hanya entri dengan `reason` non-kosong (setelah formatQuoteReason) yang dipakai di UI.
 */
function collectRelevantEvidence(rec, confirmedPills = []) {
    const ev = rec?.supporting_evidence || {};
    const pillSet = new Set(
        (Array.isArray(confirmedPills) ? confirmedPills : []).map((p) => String(p).trim().toLowerCase()),
    );
    const seen = new Set();
    const out = [];

    function pushQuote(quoteText, meta = {}) {
        const q = String(quoteText ?? '').trim();
        if (q.length < 10) return;
        const key = quoteDedupeKey(q);
        if (seen.has(key)) return;
        seen.add(key);
        out.push({ quote: q, ...meta });
    }

    const reviewQuotes = Array.isArray(ev.review_quotes) ? ev.review_quotes : [];

    for (const item of reviewQuotes) {
        if (out.length >= 12) break;
        const pill = String(item?.pill || '').toLowerCase();
        const matchesPreference =
            pillSet.size === 0 ||
            pillSet.has(pill) ||
            pill === 'search_keywords' ||
            pill === 'llm_preference';
        if (!matchesPreference) continue;
        pushQuote(item.quote, {
            username: item.username,
            rating: item.rating,
            reason: item.reason,
            pill_label: item.pill_label,
        });
    }

    const positive = Array.isArray(ev.positive_review_quotes) ? ev.positive_review_quotes : [];
    for (const item of positive) {
        if (out.length >= 12) break;
        const terms = Array.isArray(item.matched_terms) ? item.matched_terms : [];
        const reason = terms.length ? terms.slice(0, 4).join(', ') : '';
        if (!formatQuoteReason(reason)) continue;
        pushQuote(item.quote, {
            username: item.username,
            rating: item.rating,
            reason,
            pill_label: 'Ulasan pengguna',
        });
    }

    const keywordMatches = Array.isArray(ev.search_keyword_matches) ? ev.search_keyword_matches : [];
    for (const item of keywordMatches) {
        if (out.length >= 12) break;
        const terms = Array.isArray(item.matched_terms) ? item.matched_terms : [];
        const reason = terms.length ? terms.slice(0, 4).join(', ') : '';
        if (!formatQuoteReason(reason)) continue;
        pushQuote(item.quote, {
            username: item.username,
            rating: item.rating,
            reason,
            pill_label: 'Kecocokan kata kunci',
        });
    }

    if (out.length === 0 && reviewQuotes.length > 0) {
        for (const item of reviewQuotes) {
            if (out.length >= 12) break;
            if (!formatQuoteReason(item.reason)) continue;
            pushQuote(item.quote, {
                username: item.username,
                rating: item.rating,
                reason: item.reason,
                pill_label: item.pill_label,
            });
        }
    }

    return out.filter((item) => formatQuoteReason(item.reason)).slice(0, 5);
}

function quoteCompleteness(item) {
    let n = 0;
    if (item.rating != null && item.rating !== '') n += 1;
    if (item.rating_layanan != null && item.rating_layanan !== '') n += 1;
    if (item.rating_suasana != null && item.rating_suasana !== '') n += 1;
    if (item.rating_makanan != null && item.rating_makanan !== '') n += 1;
    if (item.has_photos) n += 1;
    return n;
}

function sortModalQuotes(items) {
    return [...items].sort((a, b) => {
        const ra = parseFloat(String(a.rating), 10);
        const rb = parseFloat(String(b.rating), 10);
        const na = Number.isFinite(ra) ? ra : -1;
        const nb = Number.isFinite(rb) ? rb : -1;
        if (nb !== na) return nb - na;
        return quoteCompleteness(b) - quoteCompleteness(a);
    });
}

/**
 * Maksimal 3 bukti, urut rating tertinggi lalu kelengkapan sinyal (backend atau fallback klien).
 */
function getModalEvidenceItems(rec, confirmedPills) {
    const ev = rec?.supporting_evidence || {};
    const fromApi = Array.isArray(ev.modal_display_quotes) ? ev.modal_display_quotes : [];
    if (fromApi.length > 0) return fromApi.slice(0, 3);
    const collected = collectRelevantEvidence(rec, confirmedPills);
    return sortModalQuotes(collected).slice(0, 3);
}

function getModalSummaryText(rec) {
    const ev = rec?.supporting_evidence || {};
    const fromQuotes = String(ev.modal_quote_summary || '').trim();
    if (fromQuotes) return fromQuotes;
    return String(rec?.explanation || '').trim();
}

function RatingDetailChips({ item }) {
    const chips = [];
    if (item.rating != null && item.rating !== '') {
        chips.push({ key: 'overall', label: 'Keseluruhan', value: item.rating });
    }
    if (item.rating_layanan != null && item.rating_layanan !== '') {
        chips.push({ key: 'layanan', label: 'Layanan', value: item.rating_layanan });
    }
    if (item.rating_suasana != null && item.rating_suasana !== '') {
        chips.push({ key: 'suasana', label: 'Suasana', value: item.rating_suasana });
    }
    if (item.rating_makanan != null && item.rating_makanan !== '') {
        chips.push({ key: 'makanan', label: 'Makanan', value: item.rating_makanan });
    }
    const hasFoto = Boolean(item.has_photos);
    return (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {chips.map((c) => (
                <span
                    key={c.key}
                    className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-900 dark:bg-amber-950/50 dark:text-amber-100"
                >
                    {c.label}: ★{c.value}
                </span>
            ))}
            <span
                className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    hasFoto
                        ? 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100'
                        : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                }`}
            >
                Foto: {hasFoto ? 'Ada' : 'Tidak ada'}
            </span>
        </div>
    );
}

const RecommendationModal = ({
    isOpen,
    onClose,
    recommendations = [],
    shopsByKey = {},
    confirmedPills = [],
}) => {
    useEffect(() => {
        if (!isOpen) return undefined;
        const originalOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') onClose?.();
        };
        window.addEventListener('keydown', handleKeyDown);

        return () => {
            document.body.style.overflow = originalOverflow;
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const items = recommendations
        .map((rec) => {
            const shop =
                (rec.place_id && shopsByKey[rec.place_id]) ||
                (rec.name && shopsByKey[normalizeMatchText(rec.name)]) ||
                null;
            return { rec, shop };
        })
        .filter((entry) => entry.shop);

    const confirmedLabels = pillLabelsFromValues(confirmedPills);

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby="recommendation-modal-title"
        >
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
                aria-hidden="true"
            />

            <div className="relative z-10 w-full max-w-5xl max-h-[90vh] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
                <div className="flex items-start justify-between gap-3 px-5 sm:px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-indigo-50 via-violet-50 to-indigo-50 dark:from-indigo-950/40 dark:via-violet-950/40 dark:to-indigo-950/40">
                    <div className="min-w-0">
                        <h2
                            id="recommendation-modal-title"
                            className="mt-1 text-lg sm:text-xl font-bold text-gray-900 dark:text-white"
                        >
                            Rekomendasi Coffee Shop Untuk Anda
                        </h2>
                        {confirmedLabels.length > 0 && (
                            <p className="mt-1 text-xs sm:text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                                Konteks:{' '}
                                <span className="font-medium text-gray-800 dark:text-gray-100">
                                    {confirmedLabels.join(', ')}
                                </span>
                            </p>
                        )}
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="flex-shrink-0 inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/80 text-gray-600 hover:bg-white hover:text-gray-900 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 shadow-sm transition-colors"
                        aria-label="Tutup rekomendasi"
                    >
                        <svg
                            className="w-5 h-5"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                        >
                            <path
                                fillRule="evenodd"
                                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                                clipRule="evenodd"
                            />
                        </svg>
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto px-5 sm:px-6 py-5 bg-gray-50/60 dark:bg-gray-900">
                    {!items.length ? (
                        <div className="py-10 text-gray-600 dark:text-gray-400 text-sm text-center">
                            Belum ada rekomendasi untuk ditampilkan. Tutup modal dan coba konteks lain di beranda.
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900/80">
                                <ul className="space-y-4">
                                    {items.map(({ rec, shop }, index) => {
                                        const shopName = getShopDisplayName(rec, shop);
                                        const placeId = shop?.place_id || rec?.place_id;
                                        const evidenceItems = getModalEvidenceItems(rec, confirmedPills);
                                        const summaryText = getModalSummaryText(rec);
                                        return (
                                            <li
                                                key={rec.place_id || `${rec.name}-${index}`}
                                                className="rounded-xl border border-gray-100 bg-gray-50/70 px-3 py-3 dark:border-gray-700 dark:bg-gray-900/50"
                                            >
                                                {placeId ? (
                                                    <Link
                                                        to={`/shop/${placeId}`}
                                                        onClick={() => onClose?.()}
                                                        className="inline-block text-sm font-semibold text-indigo-600 hover:text-indigo-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 rounded dark:text-indigo-300 dark:hover:text-indigo-200 dark:focus-visible:ring-offset-gray-900"
                                                    >
                                                        {shopName}
                                                    </Link>
                                                ) : (
                                                    <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                                        {shopName}
                                                    </p>
                                                )}
                                                {summaryText ? (
                                                    <p className="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-200">
                                                        {summaryText}
                                                    </p>
                                                ) : null}
                                                <div className="mt-3 space-y-2">
                                                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                                                        Bukti ulasan relevan (maks. 3)
                                                    </p>
                                                    {evidenceItems.length > 0 ? (
                                                        evidenceItems.map((quoteItem, qIdx) => (
                                                            <div
                                                                key={`${quoteDedupeKey(quoteItem.quote)}-${qIdx}`}
                                                                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
                                                            >
                                                                <p className="italic text-gray-800 dark:text-gray-100">
                                                                    &ldquo;{quoteItem.quote}&rdquo;
                                                                </p>
                                                                <RatingDetailChips item={quoteItem} />
                                                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                                    {quoteItem.username || 'Anonim'}
                                                                    {quoteItem.pill_label
                                                                        ? ` `
                                                                        : ''}
                                                                    {quoteItem.reason
                                                                        ? ` · ${formatQuoteReason(quoteItem.reason)}`
                                                                        : ''}
                                                                </p>
                                                            </div>
                                                        ))
                                                    ) : (
                                                        <p className="text-sm text-gray-600 dark:text-gray-300">
                                                            Belum ada kutipan ulasan yang cocok dengan preferensi untuk toko ini.
                                                        </p>
                                                    )}
                                                </div>
                                            </li>
                                        );
                                    })}
                                </ul>
                            </div>
                        </div>
                    )}
                </div>

                <div className="px-5 sm:px-6 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex justify-end">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 rounded-full text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                    >
                        Tutup
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RecommendationModal;
