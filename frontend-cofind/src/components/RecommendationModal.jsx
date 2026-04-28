// src/components/RecommendationModal.jsx
import React, { useEffect } from 'react';
import CoffeeShopCard from './CoffeeShopCard';

function normalizeMatchText(value) {
    return String(value ?? '').trim().toLowerCase();
}

function formatQuoteReason(value) {
    const text = String(value ?? '').trim();
    if (!text) return '';
    return text
        .replace(/^review menyebut:\s*/i, '')
        .replace(/^komentar menyebut:\s*/i, '')
        .replace(/"/g, '');
}

function getDiverseQuotes(quotes, preferredPills = [], limit = 3) {
    if (!Array.isArray(quotes) || quotes.length === 0) {
        return [];
    }

    const normalizedPreferredPills = preferredPills
        .map((pill) => normalizeMatchText(pill))
        .filter(Boolean);

    const uniqueQuotes = [];
    const seenQuotes = new Set();

    quotes.forEach((item) => {
        const quoteKey = normalizeMatchText(item?.quote);
        if (!quoteKey || seenQuotes.has(quoteKey)) {
            return;
        }
        seenQuotes.add(quoteKey);
        uniqueQuotes.push(item);
    });

    if (normalizedPreferredPills.length <= 1) {
        return uniqueQuotes.slice(0, limit);
    }

    const selected = [];
    const usedIndices = new Set();

    normalizedPreferredPills.forEach((pill) => {
        const quoteIndex = uniqueQuotes.findIndex(
            (item, index) =>
                !usedIndices.has(index) &&
                normalizeMatchText(item?.pill) === pill
        );

        if (quoteIndex >= 0 && selected.length < limit) {
            selected.push(uniqueQuotes[quoteIndex]);
            usedIndices.add(quoteIndex);
        }
    });

    uniqueQuotes.forEach((item, index) => {
        if (selected.length >= limit || usedIndices.has(index)) {
            return;
        }
        selected.push(item);
        usedIndices.add(index);
    });

    return selected;
}

function buildFacilitiesEvidenceBlocks(items) {
    if (!Array.isArray(items) || items.length === 0) return [];
    return items
        .map(({ rec, shop }) => {
            const ev = rec?.supporting_evidence || {};
            const summary = String(ev.facilities_evidence_summary || '').trim();
            if (!summary) return null;
            const shopName = String(rec?.name || shop?.name || 'Coffee shop').trim();
            return {
                shopName,
                summary,
                intentAligned: ev.facilities_intent_aligned === true,
            };
        })
        .filter(Boolean);
}

function buildManualEvidenceEntries(items, limit = 6) {
    if (!Array.isArray(items) || items.length === 0) return [];
    const entries = [];
    const seenQuoteKeys = new Set();
    const perShopKeywordMap = new Map();

    items.forEach(({ rec, shop }) => {
        const shopName = String(rec?.name || shop?.name || 'Coffee shop').trim();
        const evidence = rec?.supporting_evidence || {};
        const quotes = Array.isArray(evidence.review_quotes) ? evidence.review_quotes : [];
        const shopKey = normalizeMatchText(rec?.place_id || shop?.place_id || shopName);
        if (!perShopKeywordMap.has(shopKey)) {
            perShopKeywordMap.set(shopKey, new Set());
        }
        const usedKeywords = perShopKeywordMap.get(shopKey);

        quotes.forEach((item) => {
            if (entries.length >= limit) return;
            const quoteText = String(item?.quote || '').trim();
            if (!quoteText) return;
            const quoteKey = normalizeMatchText(quoteText);
            if (!quoteKey || seenQuoteKeys.has(quoteKey)) return;

            const keywordSource = item?.pill_label || item?.pill || item?.reason || 'preferensi';
            const keywordKey = normalizeMatchText(keywordSource) || 'preferensi';
            // Batas: 1 coffee shop maksimal 1 review untuk 1 keyword.
            if (usedKeywords.has(keywordKey)) return;

            usedKeywords.add(keywordKey);
            seenQuoteKeys.add(quoteKey);
            entries.push({
                shopName,
                quote: quoteText,
                keywordLabel: String(keywordSource || 'preferensi').trim(),
                reason: formatQuoteReason(item?.reason) || '',
                username: String(item?.username || 'Anonim').trim(),
                rating: item?.rating,
            });
        });
    });

    return entries;
}

function buildManualOverview(items) {
    const firstRec = items?.[0]?.rec;
    const firstEvidence = firstRec?.supporting_evidence || {};
    const summary = firstRec?.explanation;
    const quotes = Array.isArray(firstEvidence?.review_quotes) ? firstEvidence.review_quotes : [];
    const customMatches = Array.isArray(firstEvidence?.custom_matches) ? firstEvidence.custom_matches : [];
    const pillStats = Array.isArray(firstEvidence?.pill_stats) ? firstEvidence.pill_stats : [];
    const reviewCount = firstEvidence?.review_count;
    const firstQuote = quotes.find((item) => normalizeMatchText(item?.quote));
    const firstCustomMatch = customMatches.find((item) => normalizeMatchText(item?.quote));
    const topPillStat = pillStats.find((item) => Number(item?.keyword_review_hits) > 0);
    const evidenceEntries = buildManualEvidenceEntries(items, 6);
    const facilitiesEvidenceBlocks = buildFacilitiesEvidenceBlocks(items);

    let generatedSummary = summary;
    if (!generatedSummary) {
        if (typeof reviewCount === 'number' && reviewCount > 0) {
            generatedSummary = `Rekomendasi ini dipilih karena sinyal review user menunjukkan kecocokan yang baik dengan preferensi Anda, didukung oleh ${reviewCount} review.`;
        } else {
            generatedSummary = 'Rekomendasi ini dipilih dari kombinasi sinyal review user dan relevansi konteks terhadap preferensi manual Anda.';
        }
    }

    if (firstQuote?.quote) {
        return {
            summary: generatedSummary,
            evidenceTitle: 'Bukti relevan dari review dan fasilitas',
            evidenceText: `"${String(firstQuote.quote).trim()}"`,
            evidenceMeta: formatQuoteReason(firstQuote.reason)
                || firstQuote.pill_label
                || 'Kutipan langsung dari review user',
            evidenceEntries,
            facilitiesEvidenceBlocks,
        };
    }

    if (firstCustomMatch?.quote) {
        return {
            summary: generatedSummary,
            evidenceTitle: 'Bukti relevan dari review dan fasilitas',
            evidenceText: `"${String(firstCustomMatch.quote).trim()}"`,
            evidenceMeta: firstCustomMatch.label || 'Kutipan langsung dari review user',
            evidenceEntries,
            facilitiesEvidenceBlocks,
        };
    }

    if (topPillStat) {
        return {
            summary: generatedSummary,
            evidenceTitle: 'Bukti relevan dari review dan fasilitas',
            evidenceText: `${topPillStat.keyword_review_hits} review menyebut sinyal terkait ${topPillStat.pill_label || topPillStat.pill || 'preferensi ini'}.`,
            evidenceMeta: 'Ringkasan sinyal dari review user',
            evidenceEntries,
            facilitiesEvidenceBlocks,
        };
    }

    return {
        summary: generatedSummary,
        evidenceTitle: 'Bukti relevan dari review dan fasilitas',
        evidenceText: 'Belum ada kutipan review yang cukup kuat untuk ditampilkan pada overview.',
        evidenceMeta: 'Silakan cek kartu rekomendasi untuk detail bukti lainnya',
        evidenceEntries,
        facilitiesEvidenceBlocks,
    };
}

const RecommendationModal = ({
    isOpen,
    onClose,
    recommendations = [],
    shopsByKey = {},
    confirmedPills = [],
    confirmedCustomQuery = '',
    /** 'pills' = hanya hasil; 'manual' = form input + hasil di modal yang sama */
    modalMode = 'pills',
    manualValue = '',
    onManualChange,
    onManualAnalyze,
    manualError = '',
    manualCharCount = 0,
    manualMaxChars = 20,
    manualAnalyzeDisabled = false,
    /** Loading analisis di dalam modal (mode manual) */
    isAnalyzing = false,
    /** Sebelum user menekan Analisis: tampilkan petunjuk, bukan pesan maaf */
    manualAwaitingFirstSearch = false,
    /** Pesan status dari backend/UI (mis. reject option) */
    manualStatusMessage = '',
    /** Daftar pill saran yang bisa ditekan langsung */
    suggestedPills = [],
    onSuggestedPillClick,
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
    const isManualPanel = modalMode === 'manual';
    const isManualMode = Boolean(confirmedCustomQuery.trim());

    const items = recommendations
        .map((rec) => {
            const shop =
                (rec.place_id && shopsByKey[rec.place_id]) ||
                (rec.name && shopsByKey[normalizeMatchText(rec.name)]) ||
                null;
            return { rec, shop };
        })
        .filter((entry) => entry.shop);

    const manualOverviewData = buildManualOverview(items);

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
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-500 dark:text-indigo-300">
                            AI Recommendation
                        </p>
                        <h2
                            id="recommendation-modal-title"
                            className="mt-1 text-lg sm:text-xl font-bold text-gray-900 dark:text-white"
                        >
                            {isManualPanel
                                ? 'Preferensi lainnya'
                                : 'Rekomendasi Coffee Shop Untuk Anda'}
                        </h2>
                        {isManualPanel && (
                            <p className="mt-1 text-xs sm:text-sm text-gray-600 dark:text-gray-300">
                                Tulis preferensi bebas Anda dengan jelas dan utuh (hindari singkatan yang bisa
                                ditafsir berbeda), lalu tekan <span className="font-medium">Analisis</span>.
                                Ringkasan LLM dan bukti review akan tampil di bawah.
                            </p>
                        )}
                        {!isManualPanel && (confirmedPills.length > 0 || confirmedCustomQuery.trim()) && (
                            <p className="mt-1 text-xs sm:text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                                {confirmedPills.length > 0 && (
                                    <>
                                        Preferensi:{' '}
                                        <span className="font-medium text-gray-800 dark:text-gray-100">
                                            {confirmedPills.join(', ')}
                                        </span>
                                    </>
                                )}
                                {confirmedPills.length > 0 && confirmedCustomQuery.trim() && (
                                    <span className="mx-1">·</span>
                                )}
                                {confirmedCustomQuery.trim() && (
                                    <>
                                        Lainnya:{' '}
                                        <span className="font-medium text-gray-800 dark:text-gray-100">
                                            {confirmedCustomQuery.trim()}
                                        </span>
                                    </>
                                )}
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
                    {isManualPanel && (
                        <div className="mb-6 rounded-2xl border border-indigo-100 bg-white px-4 py-4 shadow-sm dark:border-indigo-900/50 dark:bg-gray-800">
                            <label
                                htmlFor="manual-preference-modal-input"
                                className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5"
                            >
                                Preferensi Anda
                            </label>
                            <textarea
                                id="manual-preference-modal-input"
                                value={manualValue}
                                onChange={(e) => onManualChange?.(e)}
                                disabled={isAnalyzing}
                                rows={2}
                                maxLength={manualMaxChars}
                                placeholder="Contoh: wifi cepat, tempat tenang, parkir luas"
                                className="w-full px-3 py-2 rounded-xl border text-sm border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-y min-h-[2.75rem] disabled:opacity-60"
                            />
                            <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                                Input: {manualCharCount}/{manualMaxChars} karakter.
                            </p>
                            {!!manualError && (
                                <p className="text-xs text-red-600 dark:text-red-300 mt-1">{manualError}</p>
                            )}
                            <div className="mt-3 flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => onManualAnalyze?.()}
                                    disabled={isAnalyzing || manualAnalyzeDisabled}
                                    className="px-4 py-2 rounded-full text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                                >
                                    {isAnalyzing ? 'Menganalisis…' : 'Analisis'}
                                </button>
                            </div>
                        </div>
                    )}

                    {isAnalyzing && (
                        <div className="flex flex-col items-center justify-center py-10 text-center">
                            <div className="relative mb-4">
                                <div className="h-12 w-12 rounded-full border-4 border-indigo-100 dark:border-indigo-900/50" />
                                <div className="absolute inset-0 h-12 w-12 animate-spin rounded-full border-4 border-transparent border-t-indigo-600 border-r-violet-500" />
                            </div>
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-500 dark:text-indigo-300">
                                AI sedang bekerja
                            </p>
                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 max-w-md">
                                LLM sedang menganalisis preferensi Anda dan mencocokkannya dengan review user serta
                                sinyal tab fasilitas.
                            </p>
                        </div>
                    )}

                    {!isAnalyzing && items.length === 0 ? (
                        <div className="py-10 text-gray-600 dark:text-gray-400">
                            <p className="text-sm leading-relaxed">
                                {isManualPanel && manualAwaitingFirstSearch ? (
                                    <>
                                        Isi kolom di atas dengan preferensi bebas (maks.{' '}
                                        {manualMaxChars} karakter), lalu tekan <strong>Analisis</strong> untuk
                                        melihat rekomendasi.
                                    </>
                                ) : (
                                    <>
                                        {manualStatusMessage || 'Sistem belum mengerti preferensi Anda. Coba gunakan preferensi lain.'}
                                    </>
                                )}
                            </p>
                            {isManualPanel && suggestedPills.length > 0 && !manualAwaitingFirstSearch && (
                                <div className="mt-4 rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4 dark:border-indigo-900/50 dark:bg-indigo-950/25">
                                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                                        Coba preferensi berikut
                                    </p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        {suggestedPills.map((pill) => (
                                            <button
                                                key={pill.value}
                                                type="button"
                                                onClick={() => onSuggestedPillClick?.(pill.value)}
                                                className="px-3 py-1.5 rounded-full text-xs font-semibold bg-white text-indigo-700 border border-indigo-200 hover:bg-indigo-600 hover:text-white hover:border-indigo-600 dark:bg-gray-900 dark:text-indigo-200 dark:border-indigo-800 dark:hover:bg-indigo-600 dark:hover:text-white transition-colors"
                                            >
                                                {pill.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : !isAnalyzing && isManualPanel ? (
                        <div className="space-y-4">
                            <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 p-4 shadow-sm dark:border-indigo-900/50 dark:bg-indigo-950/25">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-indigo-500 dark:text-indigo-300">
                                    Overview
                                </p>
                                <p className="mt-1.5 text-sm leading-6 text-indigo-950 dark:text-indigo-100">
                                    {manualOverviewData.summary}
                                </p>
                                <div className="mt-3 rounded-xl border border-indigo-200/80 bg-white/80 px-3 py-2.5 dark:border-indigo-800/60 dark:bg-gray-900/40">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-indigo-500/90 dark:text-indigo-300/90">
                                        {manualOverviewData.evidenceTitle}
                                    </p>
                                    <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                                        Gabungan kutipan review user dan sinyal tab fasilitas yang mendukung rekomendasi.
                                    </p>
                                    {Array.isArray(manualOverviewData.evidenceEntries) && manualOverviewData.evidenceEntries.length > 0 ? (
                                        <div className="mt-2 space-y-2">
                                            {manualOverviewData.evidenceEntries.map((entry, idx) => (
                                                <div
                                                    key={`${entry.shopName}-${entry.quote}-${idx}`}
                                                    className="rounded-lg border border-indigo-100 bg-white/90 px-3 py-2 dark:border-indigo-900/50 dark:bg-gray-900/60"
                                                >
                                                    <p className="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                                                        {entry.keywordLabel}
                                                    </p>
                                                    <p className="mt-1 text-sm leading-6 text-gray-800 dark:text-gray-100">
                                                        "{entry.quote}"
                                                    </p>
                                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                        {entry.username} · {entry.shopName}
                                                        {entry.rating ? ` · ★ ${entry.rating}` : ''}
                                                        {entry.reason ? ` · ${entry.reason}` : ''}
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <>
                                            <p className="mt-1 text-sm leading-6 text-gray-800 dark:text-gray-100">
                                                {manualOverviewData.evidenceText}
                                            </p>
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                {manualOverviewData.evidenceMeta}
                                            </p>
                                        </>
                                    )}
                                    {Array.isArray(manualOverviewData.facilitiesEvidenceBlocks) &&
                                        manualOverviewData.facilitiesEvidenceBlocks.length > 0 && (
                                            <div className="mt-2 space-y-2">
                                                {manualOverviewData.facilitiesEvidenceBlocks.map((block, bIdx) => (
                                                    <div
                                                        key={`${block.shopName}-fac-${bIdx}`}
                                                        className="rounded-lg border border-teal-100 bg-teal-50/80 px-3 py-2 dark:border-teal-900/40 dark:bg-teal-950/20"
                                                    >
                                                        <p className="text-xs font-semibold text-teal-800 dark:text-teal-200">
                                                            Fasilitas · {block.shopName}
                                                            {block.intentAligned ? (
                                                                <span className="ml-1.5 font-normal text-teal-600 dark:text-teal-400">
                                                                    (selaras preferensi)
                                                                </span>
                                                            ) : null}
                                                        </p>
                                                        <p className="mt-1 text-sm leading-6 text-gray-800 dark:text-gray-100">
                                                            {block.summary}
                                                        </p>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                </div>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                {items.map(({ rec, shop }, index) => (
                                    <div
                                        key={rec.place_id || `${rec.name}-${index}`}
                                        className="space-y-2"
                                    >
                                        <div className="inline-flex items-center rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 px-3 py-1 text-xs font-semibold text-white">
                                            Rekomendasi #{index + 1}
                                        </div>
                                        <CoffeeShopCard shop={shop} variant="mini" />
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : !isAnalyzing ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                            {items.map(({ rec, shop }, index) => {
                                const evidence = rec.supporting_evidence || {};
                                const quotes = Array.isArray(evidence.review_quotes)
                                    ? evidence.review_quotes
                                    : [];
                                const pillStats = Array.isArray(evidence.pill_stats)
                                    ? evidence.pill_stats
                                    : [];
                                const reviewPills = Array.isArray(evidence.review_pills)
                                    ? evidence.review_pills
                                    : [];
                                const customMatches = Array.isArray(evidence.custom_matches)
                                    ? evidence.custom_matches
                                    : [];
                                const facilitiesEvidenceSummary = String(
                                    evidence.facilities_evidence_summary || ''
                                ).trim();
                                const facilitiesIntentAligned = evidence.facilities_intent_aligned === true;
                                const avgUserRating = evidence.avg_user_rating;
                                const reviewCount = evidence.review_count;
                                const isLowConfidence = evidence.is_low_confidence === true;
                                const displayedQuotes = getDiverseQuotes(
                                    quotes,
                                    confirmedPills,
                                    3
                                );

                                return (
                                    <div
                                        key={rec.place_id || `${rec.name}-${index}`}
                                        className="flex flex-col gap-3 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden"
                                    >
                                        <div className="relative">
                                            <div className="absolute top-2 left-2 z-20 bg-gradient-to-r from-indigo-500 to-violet-500 text-white w-9 h-9 rounded-full flex items-center justify-center font-bold text-base shadow-lg">
                                                {index + 1}
                                            </div>
                                            <CoffeeShopCard shop={shop} />
                                        </div>

                                        <div className="px-4 pb-4 flex flex-col gap-3">
                                            {isLowConfidence && (
                                                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-200">
                                                    Tempat ini belum memiliki review user. Ditampilkan sebagai pelengkap berdasarkan popularitas umum.
                                                </div>
                                            )}

                                            {(reviewCount != null || avgUserRating != null) && !isLowConfidence && (
                                                <div className="flex flex-wrap items-center gap-2 text-xs">
                                                    {reviewCount != null && (
                                                        <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 font-medium text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200">
                                                            Berdasarkan {reviewCount} review user
                                                        </span>
                                                    )}
                                                    {avgUserRating != null && (
                                                        <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-1 font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                                                            ★ {Number(avgUserRating).toFixed(1)} rating user
                                                        </span>
                                                    )}
                                                </div>
                                            )}

                                            {rec.explanation && (
                                                <div>
                                                    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500 dark:text-indigo-300 mb-1.5">
                                                        {isManualMode ? 'Analisis LLM untuk input manual' : 'Ringkasan NLP dari LLM'}
                                                    </p>
                                                    <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-violet-50 px-4 py-3.5 text-sm leading-7 text-indigo-950 shadow-sm dark:border-indigo-900/40 dark:bg-gradient-to-br dark:from-indigo-950/40 dark:via-gray-900 dark:to-violet-950/30 dark:text-indigo-100">
                                                        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-indigo-500/80 dark:text-indigo-300/80">
                                                            {isManualMode
                                                                ? 'AI memahami konteks input Anda lalu mencocokkannya ke review user paling relevan'
                                                                : 'Kesimpulan AI berdasarkan review user'}
                                                        </p>
                                                        <p className="mt-2 text-[15px] leading-7">
                                                            {rec.explanation}
                                                        </p>
                                                    </div>
                                                </div>
                                            )}

                                            {(displayedQuotes.length > 0 || !!facilitiesEvidenceSummary) && (
                                                <div>
                                                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                                                        Bukti relevan
                                                    </p>
                                                    <div className="rounded-xl border border-gray-200 bg-gray-50/80 px-3 py-2.5 dark:border-gray-700 dark:bg-gray-700/40">
                                                        <p className="text-[11px] text-gray-500 dark:text-gray-400">
                                                            Gabungan sinyal dari review user dan data fasilitas toko.
                                                        </p>
                                                        {!!facilitiesEvidenceSummary && (
                                                            <div className="mt-2 rounded-lg border border-teal-100 bg-teal-50/80 px-3 py-2 text-sm leading-6 text-gray-800 dark:border-teal-900/45 dark:bg-teal-950/20 dark:text-gray-100">
                                                                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-teal-700 dark:text-teal-300">
                                                                    Fasilitas
                                                                    {facilitiesIntentAligned
                                                                        ? ' · selaras preferensi'
                                                                        : ''}
                                                                </p>
                                                                <p>{facilitiesEvidenceSummary}</p>
                                                            </div>
                                                        )}
                                                        {displayedQuotes.length > 0 && (
                                                            <div className="mt-2 space-y-2">
                                                                {displayedQuotes.map((item, qIndex) => (
                                                                    <div
                                                                        key={`${item.quote}-${qIndex}`}
                                                                        className="rounded-lg border border-indigo-100 bg-white px-3 py-2 text-sm text-gray-700 dark:border-indigo-900/40 dark:bg-gray-900/55 dark:text-gray-200"
                                                                    >
                                                                        {item.pill_label && (
                                                                            <span className="mb-1 inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-200">
                                                                                Review · {item.pill_label}
                                                                            </span>
                                                                        )}
                                                                        {item.reason && (
                                                                            <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
                                                                                {formatQuoteReason(item.reason)}
                                                                                {item.username
                                                                                    ? ` · ${item.username}`
                                                                                    : ''}
                                                                                {item.rating
                                                                                    ? ` · ★ ${item.rating}`
                                                                                    : ''}
                                                                            </p>
                                                                        )}
                                                                        <p className="italic leading-relaxed">
                                                                            "{item.quote}"
                                                                        </p>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {pillStats.length > 0 && (
                                                <div>
                                                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                                                        Sinyal per preferensi
                                                    </p>
                                                    <ul className="space-y-1.5 text-sm text-gray-700 dark:text-gray-300">
                                                        {pillStats.slice(0, 3).map((item, pIndex) => (
                                                            <li
                                                                key={`pillstat-${item.pill || pIndex}`}
                                                                className="rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-700/50"
                                                            >
                                                                <p className="font-medium text-gray-800 dark:text-gray-200">
                                                                    {item.pill_label || item.pill}
                                                                </p>
                                                                <p className="mt-0.5 text-xs text-gray-600 dark:text-gray-400">
                                                                    {item.keyword_review_hits > 0 ? (
                                                                        <>
                                                                            {item.keyword_review_hits} review menyebut kata terkait
                                                                        </>
                                                                    ) : (
                                                                        'Belum ada review yang menyebut kata terkait secara eksplisit'
                                                                    )}
                                                                    {item.category_avg != null && (
                                                                        <>
                                                                            {' · '}
                                                                            rata-rata{' '}
                                                                            {item.category_field?.replace('rating_', '')}{' '}
                                                                            {Number(item.category_avg).toFixed(1)}/5
                                                                        </>
                                                                    )}
                                                                </p>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {pillStats.length === 0 && reviewPills.length > 0 && (
                                                <div>
                                                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                                                        Sinyal dari review user
                                                    </p>
                                                    <ul className="space-y-1.5 text-sm text-gray-700 dark:text-gray-300">
                                                        {reviewPills.slice(0, 2).map((item, rpIndex) => (
                                                            <li
                                                                key={`${item.pill || item.label}-${rpIndex}`}
                                                                className="rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-700/50"
                                                            >
                                                                {item.label || item.pill_label || item.pill}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {customMatches.length > 0 && (
                                                <div>
                                                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">
                                                        Kecocokan preferensi tambahan
                                                    </p>
                                                    <ul className="space-y-1.5 text-sm text-gray-700 dark:text-gray-300">
                                                        {customMatches.slice(0, 2).map((item, cmIndex) => (
                                                            <li
                                                                key={`${item.label}-${cmIndex}`}
                                                                className="rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-700/50"
                                                            >
                                                                <p>{item.label}</p>
                                                                {item.quote && (
                                                                    <p className="mt-1 italic text-xs text-gray-600 dark:text-gray-400">
                                                                        "{item.quote}"
                                                                    </p>
                                                                )}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ) : null}
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
