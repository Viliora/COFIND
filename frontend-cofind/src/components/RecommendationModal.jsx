// src/components/RecommendationModal.jsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CONTEXT_PILL_OPTIONS } from '../constants/reviewPills';
import { authService } from '../services/authService';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const DOWNVOTE_REASON_CHIPS = [
    'Tidak sesuai konteks',
    'Ulasan menyesatkan',
    'Sudah pernah ke sini & tidak cocok',
    'Tempat lain lebih relevan',
];

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
 * @param {number} maxQuotesBeforeFilter — batas kumpul mentah (lebih besar = hitung sort lebih lengkap).
 */
function gatherRelevantEvidenceEntries(rec, confirmedPills = [], maxQuotesBeforeFilter = 12) {
    const ev = rec?.supporting_evidence || {};
    const pillSet = new Set(
        (Array.isArray(confirmedPills) ? confirmedPills : []).map((p) => String(p).trim().toLowerCase()),
    );
    const seen = new Set();
    const out = [];

    function pushQuote(quoteText, meta = {}) {
        if (out.length >= maxQuotesBeforeFilter) return;
        const q = String(quoteText ?? '').trim();
        if (q.length < 10) return;
        const key = quoteDedupeKey(q);
        if (seen.has(key)) return;
        seen.add(key);
        out.push({ quote: q, ...meta });
    }

    const reviewQuotes = Array.isArray(ev.review_quotes) ? ev.review_quotes : [];

    for (const item of reviewQuotes) {
        if (out.length >= maxQuotesBeforeFilter) break;
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
        if (out.length >= maxQuotesBeforeFilter) break;
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
        if (out.length >= maxQuotesBeforeFilter) break;
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
            if (out.length >= maxQuotesBeforeFilter) break;
            if (!formatQuoteReason(item.reason)) continue;
            pushQuote(item.quote, {
                username: item.username,
                rating: item.rating,
                reason: item.reason,
                pill_label: item.pill_label,
            });
        }
    }

    return out.filter((item) => formatQuoteReason(item.reason));
}

function collectRelevantEvidence(rec, confirmedPills = []) {
    return gatherRelevantEvidenceEntries(rec, confirmedPills, 12).slice(0, 5);
}

/** Untuk urutan modal: jumlah kutipan relevan (aturan sama, kapasitas lebih besar agar beda peringkat jelas). */
function countRelevantEvidenceForSort(rec, confirmedPills = []) {
    return gatherRelevantEvidenceEntries(rec, confirmedPills, 500).length;
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
        </div>
    );
}

function ThumbUpIcon({ className = 'w-4 h-4' }) {
    return (
        <svg className={className} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933A4 4 0 006 10.333z" />
        </svg>
    );
}

function ThumbDownIcon({ className = 'w-4 h-4' }) {
    return (
        <svg className={className} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.055 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866A4 4 0 0014 9.667z" />
        </svg>
    );
}

function RecommendationFeedbackControls({
    placeId,
    preferences,
    rankPosition,
    score,
    initialVote = null,
    initialReason = '',
}) {
    const [vote, setVote] = useState(initialVote);
    const [reasonDraft, setReasonDraft] = useState(initialReason || '');
    const [showReasonPanel, setShowReasonPanel] = useState(initialVote === 'not_helpful');
    const [saving, setSaving] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');

    useEffect(() => {
        setVote(initialVote);
        setReasonDraft(initialReason || '');
        setShowReasonPanel(initialVote === 'not_helpful');
        setStatusMessage('');
        setErrorMessage('');
    }, [initialVote, initialReason, placeId]);

    const submitFeedback = async (nextVote, reasonValue = null) => {
        const token = authService.getToken();
        if (!token) {
            setErrorMessage('Login diperlukan untuk memberi feedback.');
            return;
        }
        if (!placeId) {
            setErrorMessage('Data coffee shop tidak lengkap.');
            return;
        }

        setSaving(true);
        setErrorMessage('');
        setStatusMessage('');
        try {
            const res = await fetch(`${API_BASE}/api/recommend-by-preferences/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    place_id: placeId,
                    preferences,
                    vote: nextVote,
                    reason: reasonValue,
                    rank_position: rankPosition,
                    score,
                }),
            });
            let data = null;
            try {
                data = await res.json();
            } catch {
                data = null;
            }
            if (!res.ok || data?.status !== 'success') {
                throw new Error(data?.message || 'Gagal menyimpan feedback.');
            }

            setVote(nextVote);
            if (nextVote === 'helpful') {
                setShowReasonPanel(false);
                setStatusMessage('Terima kasih — feedback membantu kami mempertahankan rekomendasi yang relevan.');
            } else {
                setShowReasonPanel(true);
                setStatusMessage(
                    'Terima kasih — feedback “tidak relevan” disimpan untuk evaluasi dan penyempurnaan rekomendasi.',
                );
            }
            if (reasonValue != null) {
                setReasonDraft(String(reasonValue));
            }
        } catch (err) {
            setErrorMessage(err?.message || 'Gagal menyimpan feedback.');
        } finally {
            setSaving(false);
        }
    };

    const handleThumb = async (nextVote) => {
        if (saving) return;
        await submitFeedback(nextVote, nextVote === 'not_helpful' ? reasonDraft || null : null);
    };

    const handleSaveReason = async () => {
        if (saving || vote !== 'not_helpful') return;
        await submitFeedback('not_helpful', reasonDraft.trim() || null);
    };

    const applyChip = (chip) => {
        setReasonDraft((prev) => {
            const current = String(prev || '').trim();
            if (!current) return chip;
            if (current.toLowerCase().includes(chip.toLowerCase())) return current;
            return `${current}; ${chip}`;
        });
    };

    return (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white px-3 py-3 dark:border-gray-700 dark:bg-gray-900/70">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                Feedback rekomendasi
            </p>
            <p className="mt-1 text-sm text-gray-700 dark:text-gray-200">
                Apakah rekomendasi ini membantu?
            </p>
            <div className="mt-2.5 flex flex-wrap gap-2">
                <button
                    type="button"
                    disabled={saving}
                    onClick={() => handleThumb('helpful')}
                    aria-pressed={vote === 'helpful'}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-60 ${
                        vote === 'helpful'
                            ? 'bg-emerald-600 text-white shadow-sm'
                            : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-100 dark:hover:bg-emerald-900/50'
                    }`}
                >
                    <ThumbUpIcon />
                    Rekomendasi membantu
                </button>
                <button
                    type="button"
                    disabled={saving}
                    onClick={() => handleThumb('not_helpful')}
                    aria-pressed={vote === 'not_helpful'}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-60 ${
                        vote === 'not_helpful'
                            ? 'bg-rose-600 text-white shadow-sm'
                            : 'bg-rose-50 text-rose-800 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-100 dark:hover:bg-rose-900/50'
                    }`}
                >
                    <ThumbDownIcon />
                    Tidak relevan
                </button>
            </div>

            {showReasonPanel ? (
                <div className="mt-3 space-y-2 border-t border-gray-100 pt-3 dark:border-gray-800">
                    <p className="text-xs text-gray-600 dark:text-gray-300">
                        Opsional: beri alasan singkat agar evaluasi sistem lebih akurat.
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        {DOWNVOTE_REASON_CHIPS.map((chip) => (
                            <button
                                key={chip}
                                type="button"
                                disabled={saving}
                                onClick={() => applyChip(chip)}
                                className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
                            >
                                {chip}
                            </button>
                        ))}
                    </div>
                    <textarea
                        value={reasonDraft}
                        onChange={(e) => setReasonDraft(e.target.value)}
                        rows={2}
                        maxLength={500}
                        placeholder="Contoh: Suasananya terlalu ramai untuk belajar…"
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:focus:ring-indigo-900/50"
                    />
                    <div className="flex justify-end">
                        <button
                            type="button"
                            disabled={saving}
                            onClick={handleSaveReason}
                            className="rounded-full bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-60"
                        >
                            Simpan alasan
                        </button>
                    </div>
                </div>
            ) : null}

            {statusMessage ? (
                <p className="mt-2 text-xs text-emerald-700 dark:text-emerald-300" role="status">
                    {statusMessage}
                </p>
            ) : null}
            {errorMessage ? (
                <p className="mt-2 text-xs text-rose-600 dark:text-rose-300" role="alert">
                    {errorMessage}
                </p>
            ) : null}
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
    const [feedbackByPlaceId, setFeedbackByPlaceId] = useState({});

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

    useEffect(() => {
        if (!isOpen) {
            setFeedbackByPlaceId({});
            return undefined;
        }

        const placeIds = (Array.isArray(recommendations) ? recommendations : [])
            .map((rec) => String(rec?.place_id || '').trim())
            .filter(Boolean);
        const pills = (Array.isArray(confirmedPills) ? confirmedPills : [])
            .map((p) => String(p || '').trim())
            .filter(Boolean);
        const token = authService.getToken();

        if (!token || !pills.length || !placeIds.length) {
            setFeedbackByPlaceId({});
            return undefined;
        }

        let cancelled = false;
        const loadFeedback = async () => {
            try {
                const params = new URLSearchParams({
                    preferences: pills.join(','),
                    place_ids: placeIds.join(','),
                });
                const res = await fetch(
                    `${API_BASE}/api/recommend-by-preferences/feedback?${params.toString()}`,
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                    },
                );
                const data = await res.json().catch(() => null);
                if (cancelled) return;
                if (res.ok && data?.status === 'success') {
                    setFeedbackByPlaceId(data.feedback_by_place_id || {});
                } else {
                    setFeedbackByPlaceId({});
                }
            } catch {
                if (!cancelled) setFeedbackByPlaceId({});
            }
        };

        loadFeedback();
        return () => {
            cancelled = true;
        };
    }, [isOpen, recommendations, confirmedPills]);

    if (!isOpen) return null;

    const items = recommendations
        .map((rec, apiIndex) => {
            const shop =
                (rec.place_id && shopsByKey[rec.place_id]) ||
                (rec.name && shopsByKey[normalizeMatchText(rec.name)]) ||
                null;
            return { rec, shop, apiIndex };
        })
        .filter((entry) => entry.shop)
        .sort((a, b) => {
            const ca = countRelevantEvidenceForSort(a.rec, confirmedPills);
            const cb = countRelevantEvidenceForSort(b.rec, confirmedPills);
            if (cb !== ca) return cb - ca;
            const sa = Number(a.rec?.score);
            const sb = Number(b.rec?.score);
            const na = Number.isFinite(sa) ? sa : -Infinity;
            const nb = Number.isFinite(sb) ? sb : -Infinity;
            if (nb !== na) return nb - na;
            return a.apiIndex - b.apiIndex;
        })
        .map(({ rec, shop }, displayIndex) => ({ rec, shop, displayIndex }));

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
                                    {items.map(({ rec, shop, displayIndex }) => {
                                        const shopName = getShopDisplayName(rec, shop);
                                        const placeId = shop?.place_id || rec?.place_id;
                                        const evidenceItems = getModalEvidenceItems(rec, confirmedPills);
                                        const summaryText = getModalSummaryText(rec);
                                        const existingFb = placeId ? feedbackByPlaceId[placeId] : null;
                                        return (
                                            <li
                                                key={rec.place_id || `${rec.name}-${displayIndex}`}
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
                                                        Bukti ulasan relevan
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

                                                <RecommendationFeedbackControls
                                                    placeId={placeId}
                                                    preferences={confirmedPills}
                                                    rankPosition={displayIndex + 1}
                                                    score={rec?.score}
                                                    initialVote={existingFb?.vote || null}
                                                    initialReason={existingFb?.reason || ''}
                                                />
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
