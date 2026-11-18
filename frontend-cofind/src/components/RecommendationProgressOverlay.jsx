// src/components/RecommendationProgressOverlay.jsx
import React, { useEffect, useState } from 'react';

function formatElapsedSeconds(totalSec) {
    const n = Math.max(0, Math.floor(Number(totalSec) || 0));
    return n === 1 ? '1 detik' : `${n} detik`;
}

/** Tahap pipeline rekomendasi — teks ditulis untuk user, bukan istilah teknis. */
const STAGE_SEQUENCE = [
    {
        stage: 'start',
        label: 'Memahami konteks Anda',
        hint: 'Kami menyiapkan preferensi aktivitas yang Anda pilih.',
    },
    {
        stage: 'profiles',
        label: 'Mengumpulkan ulasan pengunjung',
        hint: 'Membaca pengalaman nyata dari coffee shop di Cofind.',
    },
    {
        stage: 'scoring',
        label: 'Mencari tempat yang relevan',
        hint: 'Mencocokkan ulasan dengan kebutuhan Anda, termasuk makna yang ditulis dengan kata berbeda.',
    },
    {
        stage: 'rerank',
        label: 'Memilih yang paling cocok',
        hint: 'AI membaca ulasan, memilah kelebihan dan catatan, lalu memilih hingga tiga tempat terbaik.',
    },
    {
        stage: 'summary',
        label: 'Menyusun rekomendasi untuk Anda',
        hint: 'Merangkum alasan rekomendasi dari ulasan pengunjung — tahap ini biasanya paling lama.',
    },
];

function resolveActiveIndex(stage) {
    if (stage === 'done') return STAGE_SEQUENCE.length;
    const idx = STAGE_SEQUENCE.findIndex((s) => s.stage === stage);
    return idx === -1 ? 0 : idx;
}

function StageStatusIcon({ done, current }) {
    if (done) {
        return (
            <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cofind-secondary text-[11px] text-cofind-on-secondary"
                aria-hidden="true"
            >
                ✓
            </span>
        );
    }
    if (current) {
        return (
            <span
                className="relative flex h-5 w-5 shrink-0 items-center justify-center"
                aria-hidden="true"
            >
                <span className="absolute inset-0 animate-ping rounded-full bg-cofind-primary/25" />
                <span className="relative h-2.5 w-2.5 rounded-full bg-cofind-primary" />
            </span>
        );
    }
    return (
        <span
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-cofind-rule"
            aria-hidden="true"
        />
    );
}

export default function RecommendationProgressOverlay({ open, progress, startedAtMs = null }) {
    const [elapsedSec, setElapsedSec] = useState(0);

    useEffect(() => {
        if (!open || startedAtMs == null) {
            setElapsedSec(0);
            return undefined;
        }
        const tick = () => {
            setElapsedSec(Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000)));
        };
        tick();
        const id = window.setInterval(tick, 1000);
        return () => window.clearInterval(id);
    }, [open, startedAtMs]);

    if (!open) return null;

    const activeStage = progress?.stage || 'start';
    const activeIndex = resolveActiveIndex(activeStage);
    const currentStep = STAGE_SEQUENCE[activeIndex] || STAGE_SEQUENCE[0];
    const isFinishing = activeStage === 'done';

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-cofind-ink/45 backdrop-blur-sm" aria-hidden="true" />
            <div
                className="relative z-10 w-full max-w-md rounded-panel border border-cofind-rule bg-cofind-surface px-6 py-7 shadow-cofind-lg"
                role="status"
                aria-live="polite"
                aria-busy={!isFinishing}
            >
                <div className="flex flex-col items-center text-center">
                    <div className="relative mb-5">
                        <div className="h-14 w-14 rounded-full border-4 border-cofind-rule" />
                        <div className="absolute inset-0 h-14 w-14 animate-spin rounded-full border-4 border-transparent border-t-cofind-primary border-r-cofind-secondary" />
                    </div>

                    <p className="text-xs font-semibold uppercase tracking-wide text-cofind-muted">
                        Sedang mencari rekomendasi
                    </p>
                    <h3 className="mt-2 font-display text-xl font-bold text-cofind-ink">
                        {isFinishing ? 'Hampir selesai' : currentStep.label}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-cofind-muted">
                        {isFinishing
                            ? 'Rekomendasi akan segera ditampilkan.'
                            : currentStep.hint}
                    </p>
                    {startedAtMs != null ? (
                        <p
                            className="mt-3 inline-flex items-center rounded-full border border-cofind-rule bg-cofind-paper px-3 py-1 text-xs font-medium tabular-nums text-cofind-ink"
                            aria-live="off"
                        >
                            Waktu berjalan: {formatElapsedSeconds(elapsedSec)}
                        </p>
                    ) : null}

                    <ol className="mt-6 w-full space-y-3 rounded-panel border border-cofind-rule bg-cofind-paper px-4 py-4 text-left">
                        {STAGE_SEQUENCE.map((item, index) => {
                            const done = index < activeIndex;
                            const current = !isFinishing && index === activeIndex;
                            return (
                                <li
                                    key={item.stage}
                                    className={`flex gap-3 ${
                                        done
                                            ? 'opacity-70'
                                            : current
                                              ? ''
                                              : 'opacity-45'
                                    }`}
                                >
                                    <StageStatusIcon done={done} current={current} />
                                    <div className="min-w-0 flex-1">
                                        <p
                                            className={`text-sm leading-snug ${
                                                current
                                                    ? 'font-semibold text-cofind-ink'
                                                    : done
                                                      ? 'text-cofind-secondary'
                                                      : 'text-cofind-muted'
                                            }`}
                                        >
                                            {item.label}
                                        </p>
                                        {current ? (
                                            <p className="mt-0.5 text-xs leading-relaxed text-cofind-muted">
                                                {item.hint}
                                            </p>
                                        ) : null}
                                    </div>
                                </li>
                            );
                        })}
                    </ol>

                    <p className="mt-4 text-xs text-cofind-muted">
                        Mohon tunggu — hasil akan muncul otomatis setelah proses selesai.
                    </p>
                </div>
            </div>
        </div>
    );
}