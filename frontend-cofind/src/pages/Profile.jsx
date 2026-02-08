import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';
import ReviewCard from '../components/ReviewCard';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const Profile = () => {
  const { userId: urlUserId } = useParams();
  const { user, profile, refreshProfile, signOut } = useAuth();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [profileLoading, setProfileLoading] = useState(false);
  const [viewProfile, setViewProfile] = useState(null);
  const [viewReviews, setViewReviews] = useState([]);

  // Form state - hanya username dan nickname (full_name)
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');

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

  // Load profile data into form (hanya untuk profil saya)
  useEffect(() => {
    if (profile && isMyProfile) {
      setUsername(profile.username || '');
      setFullName(profile.full_name || '');
    }
  }, [profile, isMyProfile]);

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

  // Handle form submission - hanya update username dan nickname
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      // Update profile using authService
      const result = await authService.updateProfile({
        full_name: fullName.trim(),
        bio: '' // Can be extended later
      });

      if (!result.success) {
        setError('Gagal menyimpan profil: ' + result.error);
      } else {
        setSuccess('Profil berhasil disimpan!');
        await refreshProfile();
        setIsEditing(false);
      }
    } catch {
      setError('Terjadi kesalahan. Silakan coba lagi.');
    } finally {
      setLoading(false);
    }
  };

  // Cancel editing
  const handleCancel = () => {
    setIsEditing(false);
    setUsername(profile?.username || '');
    setFullName(profile?.full_name || '');
    setError('');
  };

  // Tampilan profil orang lain (read-only)
  if (urlUserId && !isMyProfile) {
    if (profileLoading) {
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-8 px-4 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600"></div>
        </div>
      );
    }
    if (!viewProfile) {
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-8 px-4">
          <div className="max-w-2xl mx-auto text-center py-12">
            <Link to="/" className="text-amber-600 dark:text-amber-500 hover:underline">Kembali ke Beranda</Link>
            <p className="mt-4 text-gray-600 dark:text-gray-400">Profil tidak ditemukan.</p>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-8 px-4">
        <div className="max-w-2xl mx-auto">
          <div className="mb-6">
            <Link to="/" className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-amber-600 dark:hover:text-amber-500 text-sm">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
              Kembali ke Beranda
            </Link>
          </div>
          <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-xl overflow-hidden">
            <div className="h-32 bg-gradient-to-r from-amber-500 to-orange-500"></div>
            <div className="px-6 pb-6">
              <div className="relative -mt-16 mb-4">
                <div className="w-32 h-32 rounded-full border-4 border-white dark:border-zinc-800 overflow-hidden bg-gray-200 dark:bg-zinc-700">
                  {viewProfile.avatar_url ? (
                    <img src={viewProfile.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-500 text-white text-4xl font-bold">
                      {(viewProfile.full_name || viewProfile.username || 'U').toString().charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{viewProfile.full_name || viewProfile.username || 'User'}</h1>
              <p className="text-gray-600 dark:text-gray-400">@{viewProfile.username || 'user'}</p>
              {viewProfile.bio && <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">{viewProfile.bio}</p>}
              <div className="grid grid-cols-2 gap-4 mt-6 py-4 border-t border-b border-gray-200 dark:border-zinc-700">
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{viewProfile.review_count ?? stats.reviewCount}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Total Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{viewProfile.average_rating ?? stats.averageRating}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Rating Rata-rata</p>
                </div>
              </div>
              {/* Daftar review di dalam card */}
              <div className="mt-6 pt-6 border-t border-gray-200 dark:border-zinc-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Semua Review</h2>
                {viewReviews.length === 0 ? (
                  <p className="text-gray-500 dark:text-gray-400">Belum ada review.</p>
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
    <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <Link to="/" className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-amber-600 dark:hover:text-amber-500 text-sm">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            Kembali ke Beranda
          </Link>
        </div>

        <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-xl overflow-hidden">
          <div className="h-32 bg-gradient-to-r from-amber-500 to-orange-500"></div>
          <div className="px-6 pb-6">
            <div className="relative -mt-16 mb-4">
              <div className="w-32 h-32 rounded-full border-4 border-white dark:border-zinc-800 overflow-hidden bg-gray-200 dark:bg-zinc-700">
                {profile?.avatar_url ? (
                  <img src={profile.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-500 text-white text-4xl font-bold">
                    {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                  </div>
                )}
              </div>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}
            {success && (
              <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <p className="text-sm text-green-700 dark:text-green-300">{success}</p>
              </div>
            )}

            {isEditing ? (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
                  <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent" placeholder="username_anda" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nickname</label>
                  <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent" placeholder="Nickname Anda" />
                </div>
                <div className="flex gap-3 pt-4">
                  <button type="button" onClick={handleCancel} className="flex-1 py-3 px-4 border border-gray-300 dark:border-zinc-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-zinc-700 transition-colors">Batal</button>
                  <button type="submit" disabled={loading} className="flex-1 py-3 px-4 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2">
                    {loading ? <><div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div><span>Menyimpan...</span></> : 'Simpan Perubahan'}
                  </button>
                </div>
              </form>
            ) : (
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{profile?.full_name || profile?.username || 'User'}</h1>
                <p className="text-gray-600 dark:text-gray-400">@{profile?.username || 'user'}</p>
                <div className="grid grid-cols-3 gap-4 mt-6 py-4 border-t border-b border-gray-200 dark:border-zinc-700">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.reviewCount}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Review</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.averageRating}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Rating</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.favoriteCount}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Favorit</p>
                  </div>
                </div>
                <div className="mt-6 space-y-3">
                  <button onClick={() => setIsEditing(true)} className="w-full py-3 px-4 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    Edit Profil
                  </button>
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
                    className="w-full py-3 px-4 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors flex items-center justify-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                    Keluar
                  </button>
                </div>

                {/* Daftar review saya di dalam card */}
                <div className="mt-6 pt-6 border-t border-gray-200 dark:border-zinc-700">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Semua Review Saya</h2>
                  {viewReviews.length === 0 ? (
                    <p className="text-gray-500 dark:text-gray-400">Belum ada review.</p>
                  ) : (
                    <ul className="space-y-4">
                      {viewReviews.map((r) => (
                        <li key={r.id}>
                          <a
                            href={r.place_id ? `/shop/${r.place_id}#review-${r.id}` : '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => { if (!r.place_id || e.target.closest('button')) e.preventDefault(); }}
                            className="block rounded-xl transition-all cursor-pointer hover:bg-gray-50 dark:hover:bg-zinc-700/50 hover:ring-2 hover:ring-amber-500/30 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                          >
                            <ReviewCard review={r} onDelete={() => setViewReviews((prev) => prev.filter((x) => x.id !== r.id))} onUpdate={() => {}} onLike={() => {}} />
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          Bergabung sejak {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}
        </div>
      </div>
    </div>
  );
};

export default Profile;
