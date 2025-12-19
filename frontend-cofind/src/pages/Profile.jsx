import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { supabase, updateUserProfile, uploadAvatar } from '../lib/supabase';

const Profile = () => {
  const { user, profile, refreshProfile, signOut } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Form state
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);

  // User stats
  const [stats, setStats] = useState({
    reviewCount: 0,
    favoriteCount: 0,
    wantToVisitCount: 0
  });

  // Load profile data into form
  useEffect(() => {
    if (profile) {
      setUsername(profile.username || '');
      setFullName(profile.full_name || '');
    }
  }, [profile]);

  // Load user stats
  useEffect(() => {
    const loadStats = async () => {
      if (!user || !supabase) return;

      try {
        // Get review count
        const { count: reviewCount } = await supabase
          .from('reviews')
          .select('*', { count: 'exact', head: true })
          .eq('user_id', user.id);

        // Get favorite count
        const { count: favoriteCount } = await supabase
          .from('favorites')
          .select('*', { count: 'exact', head: true })
          .eq('user_id', user.id);

        // Get want to visit count
        const { count: wantToVisitCount } = await supabase
          .from('want_to_visit')
          .select('*', { count: 'exact', head: true })
          .eq('user_id', user.id);

        setStats({
          reviewCount: reviewCount || 0,
          favoriteCount: favoriteCount || 0,
          wantToVisitCount: wantToVisitCount || 0
        });
      } catch (err) {
        console.error('Error loading stats:', err);
      }
    };

    loadStats();
  }, [user]);

  // Handle avatar file selection
  const handleAvatarChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024) {
        setError('Ukuran file maksimal 2MB');
        return;
      }
      setAvatarFile(file);
      setAvatarPreview(URL.createObjectURL(file));
    }
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      let avatarUrl = profile?.avatar_url;

      // Upload avatar if changed
      if (avatarFile) {
        const { url, error: uploadError } = await uploadAvatar(user.id, avatarFile);
        if (uploadError) {
          setError('Gagal mengupload avatar: ' + uploadError.message);
          setLoading(false);
          return;
        }
        avatarUrl = url;
      }

      // Update profile
      const { error: updateError } = await updateUserProfile(user.id, {
        username: username.trim(),
        full_name: fullName.trim(),
        avatar_url: avatarUrl,
        updated_at: new Date().toISOString()
      });

      if (updateError) {
        if (updateError.message.includes('duplicate')) {
          setError('Username sudah digunakan');
        } else {
          setError('Gagal menyimpan profil: ' + updateError.message);
        }
      } else {
        setSuccess('Profil berhasil disimpan!');
        await refreshProfile();
        setIsEditing(false);
        setAvatarFile(null);
        setAvatarPreview(null);
      }
    } catch (err) {
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
    setAvatarFile(null);
    setAvatarPreview(null);
    setError('');
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Link 
            to="/" 
            className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-amber-600 dark:hover:text-amber-500 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Kembali ke Beranda
          </Link>
        </div>

        {/* Profile Card */}
        <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-xl overflow-hidden">
          {/* Cover Image */}
          <div className="h-32 bg-gradient-to-r from-amber-500 to-orange-500"></div>

          {/* Profile Content */}
          <div className="px-6 pb-6">
            {/* Avatar */}
            <div className="relative -mt-16 mb-4">
              <div className="w-32 h-32 rounded-full border-4 border-white dark:border-zinc-800 overflow-hidden bg-gray-200 dark:bg-zinc-700">
                {(avatarPreview || profile?.avatar_url) ? (
                  <img 
                    src={avatarPreview || profile?.avatar_url} 
                    alt="Avatar" 
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-500 text-white text-4xl font-bold">
                    {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                  </div>
                )}
              </div>
              {isEditing && (
                <label className="absolute bottom-0 right-0 p-2 bg-amber-500 text-white rounded-full cursor-pointer hover:bg-amber-600 transition-colors shadow-lg">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <input 
                    type="file" 
                    accept="image/*" 
                    onChange={handleAvatarChange}
                    className="hidden"
                  />
                </label>
              )}
            </div>

            {/* Messages */}
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

            {/* Profile Form / Display */}
            {isEditing ? (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Username
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    placeholder="username_anda"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Nama Lengkap
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    placeholder="Nama Lengkap Anda"
                  />
                </div>
                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="flex-1 py-3 px-4 border border-gray-300 dark:border-zinc-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-zinc-700 transition-colors"
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 py-3 px-4 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <>
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                        <span>Menyimpan...</span>
                      </>
                    ) : (
                      'Simpan Perubahan'
                    )}
                  </button>
                </div>
              </form>
            ) : (
              <div>
                {/* Display Name */}
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {profile?.full_name || profile?.username || 'User'}
                </h1>
                <p className="text-gray-600 dark:text-gray-400">
                  @{profile?.username || 'user'}
                </p>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4 mt-6 py-4 border-t border-b border-gray-200 dark:border-zinc-700">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.reviewCount}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Review</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.favoriteCount}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Favorit</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.wantToVisitCount}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Want to Visit</p>
                  </div>
                </div>

                {/* Actions */}
                <div className="mt-6 space-y-3">
                  <button
                    onClick={() => setIsEditing(true)}
                    className="w-full py-3 px-4 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Edit Profil
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        const result = await signOut();
                        if (result?.error) {
                          console.error('[Profile] Error signing out:', result.error);
                        } else {
                          console.log('[Profile] Sign out successful');
                        }
                        // Wait a bit to ensure all state is cleared
                        await new Promise(resolve => setTimeout(resolve, 300));
                        // Navigate to home page after logout
                        window.location.href = '/';
                      } catch (error) {
                        console.error('[Profile] Error during logout:', error);
                        // Navigate to home even if there's an error
                        window.location.href = '/';
                      }
                    }}
                    className="w-full py-3 px-4 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors flex items-center justify-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    Keluar
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Member Since */}
        <div className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          Bergabung sejak {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}
        </div>
      </div>
    </div>
  );
};

export default Profile;
