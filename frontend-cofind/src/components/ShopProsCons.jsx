import React, { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

function VoteButtons({ item, disabled, onVote }) {
  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onVote(item.id, 'up')}
        className={`flex flex-col items-center gap-0.5 px-1 py-0.5 rounded transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
          item.user_vote === 'up'
            ? 'text-emerald-600 dark:text-emerald-400'
            : 'text-gray-400 hover:text-emerald-600 dark:text-gray-500 dark:hover:text-emerald-400'
        }`}
        aria-label="Upvote"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill={item.user_vote === 'up' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
          <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
        </svg>
        <span className="text-[10px] font-medium leading-none">{item.upvotes}</span>
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onVote(item.id, 'down')}
        className={`flex flex-col items-center gap-0.5 px-1 py-0.5 rounded transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
          item.user_vote === 'down'
            ? 'text-rose-600 dark:text-rose-400'
            : 'text-gray-400 hover:text-rose-600 dark:text-gray-500 dark:hover:text-rose-400'
        }`}
        aria-label="Downvote"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill={item.user_vote === 'down' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
          <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
          <path d="M17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
        </svg>
        <span className="text-[10px] font-medium leading-none">{item.downvotes}</span>
      </button>
    </div>
  );
}

export default function ShopProsCons({ placeId, user, isAuthenticated, onRequireLogin }) {
  const [pros, setPros] = useState([]);
  const [cons, setCons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [votingId, setVotingId] = useState(null);
  const [showAllPros, setShowAllPros] = useState(false);
  const [showAllCons, setShowAllCons] = useState(false);
  const MAX_VISIBLE = 5;

  const fetchProsCons = async () => {
    if (!placeId) return;
    try {
      const params = new URLSearchParams();
      if (user?.id) params.set('user_id', user.id);
      const response = await fetch(
        `${API_BASE}/api/coffeeshops/${encodeURIComponent(placeId)}/pros-cons?${params.toString()}`
      );
      if (response.ok) {
        const payload = await response.json();
        setPros(payload?.pros || []);
        setCons(payload?.cons || []);
      }
    } catch (err) {
      console.error('[ShopProsCons] Error fetching pros & cons:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchProsCons();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeId, user?.id]);

  const handleVote = async (pointId, voteType) => {
    if (!isAuthenticated || !user?.id) {
      onRequireLogin?.();
      return;
    }
    setVotingId(pointId);
    try {
      const response = await fetch(
        `${API_BASE}/api/coffeeshops/${encodeURIComponent(placeId)}/pros-cons/${pointId}/vote`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: Number(user.id), vote_type: voteType }),
        }
      );
      const payload = await response.json().catch(() => ({}));
      if (response.ok && payload?.status === 'success') {
        const applyUpdate = (list) =>
          list.map((item) =>
            item.id === pointId
              ? { ...item, upvotes: payload.upvotes, downvotes: payload.downvotes, user_vote: payload.user_vote }
              : item
          );
        setPros((prev) => applyUpdate(prev));
        setCons((prev) => applyUpdate(prev));
      }
    } catch (err) {
      console.error('[ShopProsCons] Error voting:', err);
    } finally {
      setVotingId(null);
    }
  };

  if (loading || (!pros.length && !cons.length)) {
    return null;
  }

  return (
    <div className="mt-6 sm:mt-8">
      <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white border-l-4 border-gray-400 dark:border-zinc-500 pl-3 mb-4">
        What People Say
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* PROS */}
        <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300">Pros</span>
          </div>
          {pros.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500">Belum ada data.</p>
          ) : (
            <>
              <ul className="space-y-2.5">
                {(showAllPros ? pros : pros.slice(0, MAX_VISIBLE)).map((item) => (
                  <li key={item.id} className="flex items-center gap-3">
                    <VoteButtons item={item} disabled={votingId === item.id} onVote={handleVote} />
                    <span className="text-sm text-gray-700 dark:text-gray-200">{item.text}</span>
                  </li>
                ))}
              </ul>
              {pros.length > MAX_VISIBLE && (
                <button
                  type="button"
                  onClick={() => setShowAllPros((v) => !v)}
                  className="mt-2 text-xs text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors cursor-pointer"
                >
                  {showAllPros ? 'Show less ↑' : `Show more (${pros.length - MAX_VISIBLE} more) ↓`}
                </button>
              )}
            </>
          )}
        </div>

        {/* CONS */}
        <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              </svg>
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-gray-600 dark:text-gray-300">Cons</span>
          </div>
          {cons.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500">Belum ada data.</p>
          ) : (
            <>
              <ul className="space-y-2.5">
                {(showAllCons ? cons : cons.slice(0, MAX_VISIBLE)).map((item) => (
                  <li key={item.id} className="flex items-center gap-3">
                    <VoteButtons item={item} disabled={votingId === item.id} onVote={handleVote} />
                    <span className="text-sm text-gray-700 dark:text-gray-200">{item.text}</span>
                  </li>
                ))}
              </ul>
              {cons.length > MAX_VISIBLE && (
                <button
                  type="button"
                  onClick={() => setShowAllCons((v) => !v)}
                  className="mt-2 text-xs text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors cursor-pointer"
                >
                  {showAllCons ? 'Show less ↑' : `Show more (${cons.length - MAX_VISIBLE} more) ↓`}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">
        Note: These pros and cons are AI-generated from user reviews and may be inaccurate. Please read full reviews
        and consider your own needs before decide about something in this coffee shop.
      </p>
    </div>
  );
}
