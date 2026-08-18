// src/components/RecommendationProgressOverlay.jsx
import React from 'react';

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
        stage: 'keyword_expansion',
        label: 'Mencari kata kunci yang relevan',
        hint: 'AI membantu menemukan topik ulasan yang cocok dengan kebutuhan Anda.',
    },
    {
        stage: 'scoring',
        label: 'Membandingkan tempat-tempat kandidat',
        hint: 'Menilai seberapa sering ulasan membahas hal yang Anda cari.',
    },
    {
        stage: 'rerank',
        label: 'Memilih yang paling cocok',
        hint: 'AI mengurutkan coffee shop dengan bukti ulasan terkuat.',
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
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500 text-[11px] text-white"
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
                <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/30" />
                <span className="relative h-2.5 w-2.5 rounded-full bg-indigo-600 dark:bg-indigo-400" />
            </span>
        );
    }
    return (
        <span
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-indigo-200 dark:border-indigo-800"
            aria-hidden="true"
        />
    );
}

export default function RecommendationProgressOverlay({ open, progress }) {
    if (!open) return null;

    const activeStage = progress?.stage || 'start';
    const activeIndex = resolveActiveIndex(activeStage);
    const currentStep = STAGE_SEQUENCE[activeIndex] || STAGE_SEQUENCE[0];
    const isFinishing = activeStage === 'done';

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm" aria-hidden="true" />
            <div
                className="relative z-10 w-full max-w-md rounded-3xl border border-indigo-100 bg-white px-6 py-7 shadow-2xl dark:border-indigo-900/60 dark:bg-gray-900"
                role="status"
                aria-live="polite"
                aria-busy={!isFinishing}
            >
                <div className="flex flex-col items-center text-center">
                    <div className="relative mb-5">
                        <div className="h-14 w-14 rounded-full border-4 border-indigo-100 dark:border-indigo-900/50" />
                        <div className="absolute inset-0 h-14 w-14 animate-spin rounded-full border-4 border-transparent border-t-indigo-600 border-r-violet-500" />
                    </div>

                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-indigo-500 dark:text-indigo-300">
                        Sedang mencari rekomendasi
                    </p>
                    <h3 className="mt-2 text-xl font-bold text-gray-900 dark:text-white">
                        {isFinishing ? 'Hampir selesai' : currentStep.label}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                        {isFinishing
                            ? 'Rekomendasi akan segera ditampilkan.'
                            : currentStep.hint}
                    </p>

                    <ol className="mt-6 w-full space-y-3 rounded-2xl bg-indigo-50 px-4 py-4 text-left dark:bg-indigo-950/40">
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
                                                    ? 'font-semibold text-indigo-900 dark:text-indigo-100'
                                                    : done
                                                      ? 'text-indigo-700 dark:text-indigo-200'
                                                      : 'text-gray-600 dark:text-gray-400'
                                            }`}
                                        >
                                            {item.label}
                                        </p>
                                        {current ? (
                                            <p className="mt-0.5 text-xs leading-relaxed text-indigo-800/80 dark:text-indigo-200/80">
                                                {item.hint}
                                            </p>
                                        ) : null}
                                    </div>
                                </li>
                            );
                        })}
                    </ol>

                    <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                        Mohon tunggu — hasil akan muncul otomatis setelah proses selesai.
                    </p>
                </div>
            </div>
        </div>
    );
}
