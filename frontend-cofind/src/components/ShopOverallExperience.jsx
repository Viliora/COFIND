import React, { useEffect, useState } from 'react';

const SLIDER_META = [
  { key: 'pelayanan', label: 'Pelayanan', emoji: '🛎️', color: 'bg-blue-500', accent: 'accent-blue-500' },
  { key: 'kebersihan', label: 'Kebersihan', emoji: '✨', color: 'bg-emerald-500', accent: 'accent-emerald-500' },
  { key: 'kenyamanan', label: 'Kenyamanan', emoji: '🛋️', color: 'bg-purple-500', accent: 'accent-purple-500' },
  { key: 'harga', label: 'Harga', emoji: '💰', color: 'bg-amber-500', accent: 'accent-amber-500' },
];

export const SLIDER_LABELS_MAP = {
  pelayanan: ['Buruk', 'Kurang', 'Cukup', 'Baik', 'Istimewa'],
  kebersihan: ['Kotor', 'Kurang Bersih', 'Cukup Bersih', 'Bersih', 'Sangat Bersih'],
  kenyamanan: ['Tidak Nyaman', 'Kurang Nyaman', 'Cukup Nyaman', 'Nyaman', 'Sangat Nyaman'],
  harga: ['Sangat Mahal', 'Mahal', 'Affordable', 'Murah', 'Sangat Murah'],
};

const DEFAULT_VALUES = { pelayanan: null, kebersihan: null, kenyamanan: null, harga: null };

export default function ShopOverallExperience({ summary, myVote, isAuthenticated, onSubmit, onRequireLogin }) {
  const totalVotes = summary?.total_votes || 0;

  const [values, setValues] = useState(DEFAULT_VALUES);

  useEffect(() => {
    setValues({
      pelayanan: myVote?.pelayanan ?? null,
      kebersihan: myVote?.kebersihan ?? null,
      kenyamanan: myVote?.kenyamanan ?? null,
      harga: myVote?.harga ?? null,
    });
  }, [myVote]);

  if (!totalVotes) {
    return null;
  }

  const handleChange = (key, value) => {
    const normalized = value <= 0 ? null : value;
    setValues((prev) => ({ ...prev, [key]: normalized }));
  };

  const handleCommit = (key, value) => {
    if (!isAuthenticated) {
      onRequireLogin?.();
      return;
    }
    const normalized = value <= 0 ? null : value;
    const nextValues = { ...values, [key]: normalized };
    onSubmit?.({
      presence: myVote?.presence ?? null,
      rating: myVote?.rating ?? null,
      best_for: myVote?.best_for ?? [],
      ...nextValues,
    });
  };

  return (
    <div className="mt-6 sm:mt-8">
      <div className="mb-4">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-indigo-500 text-white shadow-md text-lg">
            📊
          </span>
          Overall Experience
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 max-w-2xl">
          Rata-rata penilaian pelayanan, kebersihan, kenyamanan, dan harga berdasarkan vote pengunjung.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {SLIDER_META.map((slider) => {
          const labels = SLIDER_LABELS_MAP[slider.key];
          const distribution = summary?.slider_distributions?.[slider.key] || {};
          const maxCount = Math.max(1, ...[1, 2, 3, 4, 5].map((v) => distribution[String(v)] || 0));
          const currentValue = values[slider.key];
          const isRated = currentValue !== null && currentValue !== undefined;
          const displayValue = isRated ? currentValue : 0;
          const currentLabel = isRated ? labels[currentValue - 1] : null;

          return (
            <div
              key={slider.key}
              className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 p-4"
            >
              <div className="flex flex-col items-center text-center mb-2">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 dark:bg-zinc-700 text-lg mb-1">
                  {slider.emoji}
                </span>
                <span className="text-xs font-bold uppercase tracking-wide text-gray-700 dark:text-gray-200">
                  {slider.label}
                </span>
              </div>

              <div className="flex items-center justify-center gap-2 mb-2">
                <p className={`text-sm text-center ${isRated ? 'text-gray-700 dark:text-gray-300' : 'text-gray-400 dark:text-gray-500 italic'}`}>
                  <span className="font-semibold">{isRated ? currentLabel : 'Belum dinilai (opsional)'}</span>
                </p>
                {isRated && isAuthenticated && (
                  <button
                    type="button"
                    onClick={() => {
                      setValues((prev) => ({ ...prev, [slider.key]: null }));
                      onSubmit?.({
                        presence: myVote?.presence ?? null,
                        rating: myVote?.rating ?? null,
                        best_for: myVote?.best_for ?? [],
                        ...values,
                        [slider.key]: null,
                      });
                    }}
                    className="text-[11px] text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors cursor-pointer"
                  >
                    Hapus
                  </button>
                )}
              </div>

              <div className="mb-1">
                <input
                  type="range"
                  min={0}
                  max={5}
                  step={1}
                  list={`ticks-${slider.key}`}
                  value={displayValue}
                  disabled={!isAuthenticated}
                  onChange={(e) => handleChange(slider.key, Number(e.target.value))}
                  onMouseUp={(e) => handleCommit(slider.key, Number(e.target.value))}
                  onTouchEnd={(e) => handleCommit(slider.key, Number(e.target.value))}
                  onKeyUp={(e) => handleCommit(slider.key, Number(e.target.value))}
                  className={`w-full h-2 bg-gray-200 dark:bg-zinc-600 rounded-lg appearance-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${
                    isRated ? slider.accent : 'accent-gray-400'
                  }`}
                />
                <datalist id={`ticks-${slider.key}`}>
                  <option value="0" />
                  <option value="1" />
                  <option value="2" />
                  <option value="3" />
                  <option value="4" />
                  <option value="5" />
                </datalist>
                <div className="flex justify-between px-0.5 mt-1">
                  <span
                    key="no-vote"
                    title="No vote (default)"
                    className={`h-1.5 w-1.5 rounded-full ring-1 ring-gray-400 dark:ring-zinc-500 ${
                      !isRated ? slider.color : 'bg-transparent'
                    }`}
                  />
                  {[1, 2, 3, 4, 5].map((level) => (
                    <span
                      key={level}
                      className={`h-1.5 w-1.5 rounded-full ${
                        isRated && level <= displayValue ? slider.color : 'bg-gray-300 dark:bg-zinc-600'
                      }`}
                    />
                  ))}
                </div>
                <div className="flex justify-between px-0.5 mt-0.5">
                  <span className="text-[9px] text-gray-400 dark:text-zinc-500 -ml-1">No vote</span>
                </div>
              </div>
              {!isAuthenticated && (
                <p className="text-[11px] text-gray-400 dark:text-gray-500 text-center mb-3">
                  Login untuk memberi rating
                </p>
              )}

              {(() => {
                const allLevels = labels.map((label, idx) => ({ label, level: idx + 1 }));
                return (
                  <div className="space-y-1.5 mt-3">
                    {allLevels.map(({ label, level }) => {
                      const count = distribution[String(level)] || 0;
                      const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, count > 0 ? 6 : 0) : 0;
                      return (
                        <div key={level} className="flex items-center gap-2 text-xs">
                          <span className="w-24 text-gray-500 dark:text-gray-400 truncate">{label.toLowerCase()}</span>
                          <span className="w-6 text-right text-gray-500 dark:text-gray-400">{count}</span>
                          <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-zinc-700 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${slider.color} transition-all duration-500`}
                              style={{ width: `${pct}%`, opacity: 0.3 + level * 0.14 }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          );
        })}
      </div>
    </div>
  );
}
