import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import ReviewCard from '../components/ReviewCard';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const Profile = () => {
  const { userId: urlUserId } = useParams();
  const { user, profile, refreshProfile, signOut } = useAuth();
  const navigate = useNavigate();
  const [profileLoading, setProfileLoading] = useState(false);
  const [viewProfile, setViewProfile] = useState(null);
  const [viewReviews, setViewReviews] = useState([]);

  // User stats (untuk profil saya atau profil yang dilihat)
  const [stats, setStats] = useState({
    reviewCount: 0,
    favoriteCount: 0,
    wantToVisitCount: 0,
    averageRating: 0
  });

  const isMyProfile = !urlUserId || (user && String(user.id) === String(urlUserId));
  const targetUserId = urlUserId ? Number(urlUserId) : user?.id;

  // Title halaman: Profil [nama] - Cofind
  useEffect(() => {
    if (viewProfile?.full_name || viewProfile?.username) {
      document.title = `Profil ${viewProfile.full_name || viewProfile.username} - Cofind`;
    } else if (profile?.full_name || profile?.username) {
      document.title = `Profil ${profile.full_name || profile.username} - Cofind`;
    } else {
      document.title = 'Profil - Cofind';
    }
    return () => { document.title = 'Cofind'; };
  }, [viewProfile?.full_name, viewProfile?.username, profile?.full_name, profile?.username]);

  // Refresh profile if not loaded (profil saya)
  useEffect(() => {
    if (user && !profile && isMyProfile) {
      refreshProfile();
    }
  }, [user, profile, refreshProfile, isMyProfile]);

  // Load public profile + reviews when viewing by userId
  useEffect(() => {
    if (!targetUserId) return;

    const loadPublicProfileAndReviews = async () => {
      setProfileLoading(true);
      setViewProfile(null);
      setViewReviews([]);
      try {
        const [profileRes, reviewsRes] = await Promise.all([
          fetch(`${API_BASE}/api/users/${targetUserId}/profile`),
          fetch(`${API_BASE}/api/users/${targetUserId}/reviews?limit=100`)
        ]);
        const profileData = await profileRes.json();
        const reviewsData = await reviewsRes.json();

        if (profileData.status === 'success' && profileData.profile) {
          setViewProfile(profileData.profile);
          setStats((s) => ({
            ...s,
            reviewCount: profileData.profile.review_count ?? 0,
            averageRating: profileData.profile.average_rating ?? 0
          }));
        }
        if (reviewsData.status === 'success' && Array.isArray(reviewsData.reviews)) {
          const profileOwner = profileData.status === 'success' ? profileData.profile : null;
          const withProfile = (reviewsData.reviews || []).map((r) => ({
            ...r,
            like_count: r.like_count ?? 0,
            user_has_liked: false,
            user_total_reviews: profileOwner?.review_count ?? 0,
            profiles: profileOwner
              ? {
                  full_name: profileOwner.full_name,
                  username: profileOwner.username,
                  avatar_url: profileOwner.avatar_url
                }
              : undefined,
            full_name: profileOwner?.full_name,
            username: profileOwner?.username
          }));
          setViewReviews(withProfile);
        }
      } catch (err) {
        console.error('Error loading profile/reviews:', err);
        setViewProfile(null);
        setViewReviews([]);
      } finally {
        setProfileLoading(false);
      }
    };

    loadPublicProfileAndReviews();
  }, [targetUserId]);

  // Load stats for "my profile" (when no urlUserId, use current user)
  useEffect(() => {
    if (!user || !isMyProfile) return;

    const loadMyStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/users/${user.id}/profile`);
        const data = await res.json();
        if (data.status === 'success' && data.profile) {
          setStats((s) => ({
            ...s,
            reviewCount: data.profile.review_count ?? 0,
            averageRating: data.profile.average_rating ?? 0
          }));
        }
      } catch (err) {
        console.error('Error loading my stats:', err);
      }
    };

    loadMyStats();
  }, [user?.id, isMyProfile]);

  // Tampilan profil orang lain (read-only)
  if (urlUserId && !isMyProfile) {
    if (profileLoading) {
      return (
        <div className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 dark:from-stone-950 dark:via-stone-900 dark:to-stone-800/20 py-8 px-4 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600"></div>
        </div>
      );
    }
    if (!viewProfile) {
      return (
        <div className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 dark:from-stone-950 dark:via-stone-900 dark:to-stone-800/20 py-8 px-4">
          <div className="max-w-2xl mx-auto text-center py-12">
            <Link to="/" className="text-amber-700 dark:text-amber-400 hover:underline underline-offset-2 transition-colors">Kembali ke Beranda</Link>
            <p className="mt-4 text-stone-600 dark:text-stone-400">Profil tidak ditemukan.</p>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 dark:from-stone-950 dark:via-stone-900 dark:to-stone-800/20 py-8 px-4">
        <div className="max-w-2xl mx-auto">
          <div className="mb-6">
            <Link to="/" className="inline-flex items-center gap-2 text-stone-600 dark:text-stone-400 hover:text-amber-700 dark:hover:text-amber-400 text-sm transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
              Kembali ke Beranda
            </Link>
          </div>
          <div className="bg-[#FAF9F6]/95 dark:bg-stone-900 rounded-2xl border border-stone-200/50 dark:border-stone-700/30 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.15)] overflow-hidden">
            <div className="h-32 bg-gradient-to-r from-amber-200 to-orange-200 dark:from-stone-800 dark:to-stone-700"></div>
            <div className="px-6 pb-6">
              <div className="relative -mt-16 mb-4">
                <div className="w-32 h-32 rounded-full border-4 border-[#FAF9F6] dark:border-stone-900 overflow-hidden bg-stone-200 dark:bg-stone-700 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                  {viewProfile.avatar_url ? (
                    <img src={viewProfile.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-600 to-orange-700 text-stone-50 text-4xl font-bold">
                      {(viewProfile.full_name || viewProfile.username || 'U').toString().charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
              </div>
              <h1 className="font-serif text-2xl font-semibold text-stone-800 dark:text-stone-100">{viewProfile.full_name || viewProfile.username || 'User'}</h1>
              <p className="text-stone-600 dark:text-stone-400">@{viewProfile.username || 'user'}</p>
              {viewProfile.bio && <p className="text-sm text-stone-600 dark:text-stone-400 mt-2 font-sans leading-relaxed">{viewProfile.bio}</p>}
              <div className="grid grid-cols-2 gap-4 mt-6 py-4 border-t border-b border-stone-200/60 dark:border-stone-700/40">
                <div className="text-center">
                  <p className="text-2xl font-bold text-stone-800 dark:text-stone-100">{viewProfile.review_count ?? stats.reviewCount}</p>
                  <p className="text-sm text-stone-500 dark:text-stone-400">Total Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-stone-800 dark:text-stone-100">{viewProfile.average_rating ?? stats.averageRating}</p>
                  <p className="text-sm text-stone-500 dark:text-stone-400">Rating Rata-rata</p>
                </div>
              </div>
              {/* Daftar review di dalam card */}
              <div className="mt-6 pt-6 border-t border-stone-200/60 dark:border-stone-700/40">
                <h2 className="font-serif text-lg font-semibold text-stone-800 dark:text-stone-100 mb-4">Semua Review</h2>
                {viewReviews.length === 0 ? (
                  <p className="text-stone-500 dark:text-stone-400">Belum ada review.</p>
                ) : (
                  <ul className="space-y-4">
                    {viewReviews.map((r) => (
                      <li key={r.id}>
                        <ReviewCard review={r} onDelete={() => setViewReviews((prev) => prev.filter((x) => x.id !== r.id))} onUpdate={() => {}} onLike={() => {}} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Profil saya (perlu login, sudah di-protect oleh route)
  return (
    <div data-testid="profile-page" className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 dark:from-stone-950 dark:via-stone-900 dark:to-stone-800/20 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <Link to="/" className="inline-flex items-center gap-2 text-stone-600 dark:text-stone-400 hover:text-amber-700 dark:hover:text-amber-400 text-sm transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            Kembali ke Beranda
          </Link>
        </div>

        <div className="bg-[#FAF9F6]/95 dark:bg-stone-900 rounded-2xl border border-stone-200/50 dark:border-stone-700/30 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.15)] overflow-hidden">
          <div className="h-32 bg-gradient-to-r from-amber-200 to-orange-200 dark:from-stone-800 dark:to-stone-700"></div>
          <div className="px-6 pb-6">
            <div className="relative -mt-16 mb-4">
              <div className="w-32 h-32 rounded-full border-4 border-[#FAF9F6] dark:border-stone-900 overflow-hidden bg-stone-200 dark:bg-stone-700 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                {profile?.avatar_url ? (
                  <img src={profile.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-600 to-orange-700 text-stone-50 text-4xl font-bold">
                    {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                  </div>
                )}
              </div>
            </div>

            <div>
              <h1 data-testid="profile-display-name" className="font-serif text-2xl font-semibold text-stone-800 dark:text-stone-100">{profile?.full_name || profile?.username || 'User'}</h1>
              <p className="text-stone-600 dark:text-stone-400">@{profile?.username || 'user'}</p>
              <div className="grid grid-cols-2 gap-3 mt-6 py-4 border-t border-b border-stone-200/60 dark:border-stone-700/40">
                <div className="text-center">
                  <p className="text-2xl font-bold text-stone-800 dark:text-stone-100">{stats.reviewCount}</p>
                  <p className="text-sm text-stone-500 dark:text-stone-400">Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-stone-800 dark:text-stone-100">{stats.averageRating}</p>
                  <p className="text-sm text-stone-500 dark:text-stone-400">Rating</p>
                </div>
              </div>
              <div className="mt-6">
                <button
                  onClick={async () => {
                    try {
                      const result = await signOut();
                      if (result?.error) console.error('[Profile] Error signing out:', result.error);
                      await new Promise((r) => setTimeout(r, 300));
                      navigate('/login');
                    } catch {
                      navigate('/login');
                    }
                  }}
                  className="w-full py-3 px-4 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-xl hover:bg-red-50 dark:hover:bg-red-900/20 transition-all duration-300 ease-out cursor-pointer flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                  Keluar
                </button>
              </div>

              {/* Daftar review saya di dalam card */}
              <div className="mt-6 pt-6 border-t border-stone-200/60 dark:border-stone-700/40">
                <h2 className="font-serif text-lg font-semibold text-stone-800 dark:text-stone-100 mb-4">Semua Review Saya</h2>
                {viewReviews.length === 0 ? (
                  <p className="text-stone-500 dark:text-stone-400">Belum ada review.</p>
                ) : (
                  <ul className="space-y-4">
                    {viewReviews.map((r) => (
                      <li key={r.id}>
                        <div className="rounded-xl transition-all hover:bg-stone-50 dark:hover:bg-stone-800/50 hover:shadow-[0_12px_40px_rgb(0,0,0,0.06)] hover:-translate-y-0.5">
                          <ReviewCard review={r} onDelete={() => setViewReviews((prev) => prev.filter((x) => x.id !== r.id))} onUpdate={() => {}} onLike={() => {}} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center text-sm text-stone-500 dark:text-stone-400 font-sans">
          Bergabung sejak {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}
        </div>
      </div>
    </div>
  );
};

export default Profile;
