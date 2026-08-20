import React, { useMemo } from 'react';

function ChartCard({ title, description, children, empty = false, emptyMessage = 'Belum ada data.' }) {
  return (
    <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5">
      <div className="mb-4">
        <h4 className="text-base font-semibold text-stone-800">{title}</h4>
        {description ? <p className="mt-1 text-xs text-stone-500">{description}</p> : null}
      </div>
      {empty ? (
        <p className="text-sm text-stone-500 py-8 text-center">{emptyMessage}</p>
      ) : (
        children
      )}
    </div>
  );
}

function DonutChart({ segments, centerLabel, centerValue }) {
  const size = 160;
  const stroke = 22;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const total = segments.reduce((sum, s) => sum + (Number(s.value) || 0), 0) || 1;

  let offset = 0;
  const arcs = segments.map((segment) => {
    const value = Number(segment.value) || 0;
    const length = (value / total) * circumference;
    const arc = {
      ...segment,
      dasharray: `${length} ${circumference - length}`,
      dashoffset: -offset,
    };
    offset += length;
    return arc;
  });

  return (
    <div className="flex flex-col sm:flex-row items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e7e5e4"
            strokeWidth={stroke}
          />
          {arcs.map((arc) => (
            <circle
              key={arc.key}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={arc.color}
              strokeWidth={stroke}
              strokeDasharray={arc.dasharray}
              strokeDashoffset={arc.dashoffset}
              strokeLinecap="butt"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <p className="text-2xl font-bold text-stone-800">{centerValue}</p>
          <p className="text-[11px] text-stone-500 max-w-[90px] leading-tight">{centerLabel}</p>
        </div>
      </div>
      <div className="space-y-2 w-full">
        {segments.map((segment) => {
          const pct = total > 0 ? Math.round(((Number(segment.value) || 0) / total) * 100) : 0;
          return (
            <div key={segment.key} className="flex items-center justify-between gap-3 text-sm">
              <div className="flex items-center gap-2 min-w-0">
                <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: segment.color }} />
                <span className="text-stone-700 truncate">{segment.label}</span>
              </div>
              <span className="font-medium text-stone-800 tabular-nums">
                {segment.value}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HorizontalBars({ items, valueKey = 'value', labelKey = 'label', color = '#b45309', secondaryKey, secondaryColor = '#a8a29e' }) {
  const max = Math.max(1, ...items.map((item) => {
    const primary = Number(item[valueKey]) || 0;
    const secondary = secondaryKey ? (Number(item[secondaryKey]) || 0) : 0;
    return primary + secondary;
  }));

  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const primary = Number(item[valueKey]) || 0;
        const secondary = secondaryKey ? (Number(item[secondaryKey]) || 0) : 0;
        const primaryPct = (primary / max) * 100;
        const secondaryPct = (secondary / max) * 100;
        return (
          <div key={`${item[labelKey]}-${index}`}>
            <div className="flex items-center justify-between gap-2 mb-1">
              <p className="text-sm text-stone-700 truncate">{item[labelKey]}</p>
              <p className="text-xs text-stone-500 tabular-nums shrink-0">
                {secondaryKey
                  ? `${primary} / ${secondary}`
                  : primary}
              </p>
            </div>
            <div className="h-2.5 rounded-full bg-stone-200/80 overflow-hidden flex">
              <div className="h-full rounded-l-full" style={{ width: `${primaryPct}%`, backgroundColor: color }} />
              {secondaryKey ? (
                <div className="h-full" style={{ width: `${secondaryPct}%`, backgroundColor: secondaryColor }} />
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TrendBars({ points }) {
  const max = Math.max(1, ...points.map((p) => Number(p.count) || 0));
  return (
    <div className="flex items-end gap-1.5 h-36">
      {points.map((point) => {
        const value = Number(point.count) || 0;
        const heightPct = Math.max(value > 0 ? 8 : 2, (value / max) * 100);
        return (
          <div key={point.date} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
            <span className="text-[10px] text-stone-500 tabular-nums">{value || ''}</span>
            <div
              className="w-full rounded-t-md bg-gradient-to-t from-amber-700 to-amber-500 min-h-[2px] transition-all"
              style={{ height: `${heightPct}%` }}
              title={`${point.label}: ${value}`}
            />
            <span className="text-[10px] text-stone-400">{point.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function formatPreferenceKey(key) {
  if (!key || key === '(kosong)') return 'Tanpa preferensi';
  return String(key).split('+').map((part) => part.replace(/_/g, ' ')).join(' + ');
}

export default function AdminDashboardCharts({ charts }) {
  const feedback = charts?.recommendation_feedback || {};
  const feedbackSegments = useMemo(() => ([
    { key: 'helpful', label: 'Membantu / setuju', value: feedback.helpful || 0, color: '#15803d' },
    { key: 'not_helpful', label: 'Tidak membantu', value: feedback.not_helpful || 0, color: '#b91c1c' },
  ]), [feedback.helpful, feedback.not_helpful]);

  const suggestion = charts?.preference_suggestions || {};
  const suggestionSegments = useMemo(() => ([
    { key: 'pending', label: 'Pending', value: suggestion.pending || 0, color: '#d97706' },
    { key: 'reviewed', label: 'Direview', value: suggestion.reviewed || 0, color: '#2563eb' },
    { key: 'accepted', label: 'Diterima', value: suggestion.accepted || 0, color: '#15803d' },
    { key: 'rejected', label: 'Ditolak', value: suggestion.rejected || 0, color: '#78716c' },
  ]), [suggestion.pending, suggestion.reviewed, suggestion.accepted, suggestion.rejected]);

  const contributors = (charts?.top_contributors || []).map((row) => ({
    label: `@${row.username}`,
    value: row.review_count || 0,
    photo_count: row.photo_count || 0,
    shop_count: row.shop_count || 0,
  }));

  const shops = (charts?.most_reviewed_shops || []).map((row) => ({
    label: row.shop_name,
    value: row.review_count || 0,
    unique_reviewers: row.unique_reviewers || 0,
  }));

  const preferenceBars = (charts?.feedback_by_preference || []).map((row) => ({
    label: formatPreferenceKey(row.preferences_key),
    helpful: row.helpful || 0,
    not_helpful: row.not_helpful || 0,
  }));

  const trend = charts?.reviews_trend || [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard
          title="Feedback rekomendasi LLM"
          description="Apakah user merasa rekomendasi berbasis preferensi membantu."
          empty={(feedback.total || 0) === 0}
          emptyMessage="Belum ada feedback thumbs up/down dari rekomendasi."
        >
          <DonutChart
            segments={feedbackSegments}
            centerValue={feedback.helpful_rate != null ? `${feedback.helpful_rate}%` : '—'}
            centerLabel="tingkat membantu"
          />
          <p className="mt-4 text-xs text-stone-500">
            {feedback.total || 0} feedback dari {feedback.unique_users || 0} user.
          </p>
        </ChartCard>

        <ChartCard
          title="Saran preferensi pill"
          description="Status usulan preferensi baru dari user ke admin."
          empty={(suggestion.total || 0) === 0}
          emptyMessage="Belum ada saran preferensi."
        >
          <DonutChart
            segments={suggestionSegments.filter((s) => s.value > 0).length ? suggestionSegments : suggestionSegments}
            centerValue={suggestion.pending || 0}
            centerLabel="menunggu tinjauan"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard
          title="Kontributor pengayaan coffee shop"
          description="User yang paling banyak menambah informasi lewat review (dan foto)."
          empty={contributors.length === 0}
          emptyMessage="Belum ada kontribusi review dari user."
        >
          <HorizontalBars items={contributors} color="#b45309" />
          <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-stone-500">
            <span>Batang = jumlah review</span>
            {contributors.slice(0, 3).map((c) => (
              <span key={c.label}>
                {c.label}: {c.shop_count} toko · {c.photo_count} foto
              </span>
            ))}
          </div>
        </ChartCard>

        <ChartCard
          title="Coffee shop paling diperkaya user"
          description="Toko dengan review komunitas terbanyak."
          empty={shops.length === 0}
          emptyMessage="Belum ada coffee shop dengan review user."
        >
          <HorizontalBars items={shops} color="#0f766e" />
          <p className="mt-3 text-[11px] text-stone-500">
            Angka di kanan = total review user. Hover/lihat detail di tab Reviews.
          </p>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard
          title="Tren review 14 hari"
          description="Volume kontribusi review harian."
          empty={trend.every((p) => (p.count || 0) === 0)}
          emptyMessage="Belum ada review dalam 14 hari terakhir."
        >
          <TrendBars points={trend} />
        </ChartCard>

        <ChartCard
          title="Feedback LLM per preferensi"
          description="Hijau = membantu, abu = tidak membantu, dikelompokkan per pill."
          empty={preferenceBars.length === 0}
          emptyMessage="Belum ada feedback per preferensi."
        >
          <HorizontalBars
            items={preferenceBars}
            valueKey="helpful"
            secondaryKey="not_helpful"
            labelKey="label"
            color="#15803d"
            secondaryColor="#a8a29e"
          />
          <div className="mt-3 flex gap-4 text-[11px] text-stone-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-green-700" /> Membantu
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-stone-400" /> Tidak membantu
            </span>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}
