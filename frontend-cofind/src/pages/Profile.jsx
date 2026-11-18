import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import ReviewCard from '../components/ReviewCard';

import { API_BASE } from '../config/apiBase.js';

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
        <div className="min-h-screen bg-cofind-background py-8 px-4 flex items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-2 border-cofind-rule border-t-cofind-primary" />
        </div>
      );
    }
    if (!viewProfile) {
      return (
        <div className="min-h-screen bg-cofind-background py-8 px-4">
          <div className="max-w-2xl mx-auto text-center py-12">
            <Link to="/" className="text-cofind-secondary underline-offset-2 transition-colors hover:text-cofind-primary hover:underline">
              Kembali ke Beranda
            </Link>
            <p className="mt-4 text-cofind-muted">Profil tidak ditemukan.</p>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen bg-cofind-background py-8 px-4">
        <div className="max-w-2xl mx-auto">
          <div className="mb-6">
            <Link to="/" className="inline-flex items-center gap-2 text-sm text-cofind-muted transition-colors hover:text-cofind-secondary">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
              Kembali ke Beranda
            </Link>
          </div>
          <div className="overflow-hidden rounded-panel border border-cofind-rule bg-cofind-surface shadow-cofind-md">
            <div className="h-32 bg-cofind-primary" />
            <div className="px-6 pb-6">
              <div className="relative -mt-16 mb-4">
                <div className="h-32 w-32 overflow-hidden rounded-full border-4 border-cofind-surface bg-cofind-paper shadow-cofind-sm">
                  {viewProfile.avatar_url ? (
                    <img src={viewProfile.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-cofind-primary text-4xl font-bold text-cofind-on-primary">
                      {(viewProfile.full_name || viewProfile.username || 'U').toString().charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
              </div>
              <h1 className="font-display text-2xl font-semibold text-cofind-ink">
                {viewProfile.full_name || viewProfile.username || 'User'}
              </h1>
              <p className="text-cofind-muted">@{viewProfile.username || 'user'}</p>
              {viewProfile.bio ? (
                <p className="mt-2 font-sans text-sm leading-relaxed text-cofind-muted">{viewProfile.bio}</p>
              ) : null}
              <div className="mt-6 grid grid-cols-2 gap-4 border-y border-cofind-rule py-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-cofind-ink">{viewProfile.review_count ?? stats.reviewCount}</p>
                  <p className="text-sm text-cofind-muted">Total Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-cofind-ink">{viewProfile.average_rating ?? stats.averageRating}</p>
                  <p className="text-sm text-cofind-muted">Rating Rata-rata</p>
                </div>
              </div>
              {/* Daftar review di dalam card */}
              <div className="mt-6 border-t border-cofind-rule pt-6">
                <h2 className="mb-4 font-display text-lg font-semibold text-cofind-ink">Semua Review</h2>
                {viewReviews.length === 0 ? (
                  <p className="text-cofind-muted">Belum ada review.</p>
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
    <div data-testid="profile-page" className="min-h-screen bg-cofind-background py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <Link to="/" className="inline-flex items-center gap-2 text-sm text-cofind-muted transition-colors hover:text-cofind-secondary">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            Kembali ke Beranda
          </Link>
        </div>

        <div className="overflow-hidden rounded-panel border border-cofind-rule bg-cofind-surface shadow-cofind-md">
          <div className="h-32 bg-cofind-primary" />
          <div className="px-6 pb-6">
            <div className="relative -mt-16 mb-4">
              <div className="h-32 w-32 overflow-hidden rounded-full border-4 border-cofind-surface bg-cofind-paper shadow-cofind-sm">
                {profile?.avatar_url ? (
                  <img src={profile.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-cofind-primary text-4xl font-bold text-cofind-on-primary">
                    {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                  </div>
                )}
              </div>
            </div>

            <div>
              <h1 data-testid="profile-display-name" className="font-display text-2xl font-semibold text-cofind-ink">
                {profile?.full_name || profile?.username || 'User'}
              </h1>
              <p className="text-cofind-muted">@{profile?.username || 'user'}</p>
              <div className="mt-6 grid grid-cols-2 gap-3 border-y border-cofind-rule py-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-cofind-ink">{stats.reviewCount}</p>
                  <p className="text-sm text-cofind-muted">Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-cofind-ink">{stats.averageRating}</p>
                  <p className="text-sm text-cofind-muted">Rating</p>
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
                  className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-panel border border-red-300 px-4 py-3 text-red-700 transition-colors duration-200 hover:bg-red-50"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                  Keluar
                </button>
              </div>

              {/* Daftar review saya di dalam card */}
              <div className="mt-6 border-t border-cofind-rule pt-6">
                <h2 className="mb-4 font-display text-lg font-semibold text-cofind-ink">Semua Review Saya</h2>
                {viewReviews.length === 0 ? (
                  <p className="text-cofind-muted">Belum ada review.</p>
                ) : (
                  <ul className="space-y-4">
                    {viewReviews.map((r) => (
                      <li key={r.id}>
                        <div className="rounded-panel transition-colors hover:bg-cofind-paper">
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

        <div className="mt-6 text-center font-sans text-sm text-cofind-muted">
          Bergabung sejak {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}
        </div>
      </div>
    </div>
  );
};

export default Profile;
