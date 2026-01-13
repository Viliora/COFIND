import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import { supabase, updateUserProfile } from '../lib/supabase';
import { emergencyCleanup, getStorageInfo } from '../utils/storageCleanup';

const Profile = () => {
  const { user, profile, refreshProfile, signOut } = useAuth();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [storageInfo, setStorageInfo] = useState(null);
  
  // Form state - hanya username dan nickname (full_name)
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');

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

  // Refresh profile if not loaded
  useEffect(() => {
    if (user && !profile) {
      refreshProfile();
    }
  }, [user, profile, refreshProfile]);

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

  // Handle form submission - hanya update username dan nickname
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      // Update profile - hanya username dan full_name (nickname)
      const { error: updateError } = await updateUserProfile(user.id, {
        username: username.trim(),
        full_name: fullName.trim(),
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
            {/* Avatar - Display only (no edit) */}
            <div className="relative -mt-16 mb-4">
              <div className="w-32 h-32 rounded-full border-4 border-white dark:border-zinc-800 overflow-hidden bg-gray-200 dark:bg-zinc-700">
                {profile?.avatar_url ? (
                  <img 
                    src={profile.avatar_url} 
                    alt="Avatar" 
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-500 text-white text-4xl font-bold">
                    {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                  </div>
                )}
              </div>
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
                    Nickname
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    placeholder="Nickname Anda"
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
                        // Navigate to login page after logout
                        console.log('[Profile] Navigating to login...');
                        navigate('/login');
                      } catch (error) {
                        console.error('[Profile] Error during logout:', error);
                        // Navigate to login even if there's an error
                        navigate('/login');
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

        {/* Advanced Settings */}
        <div className="mt-6 bg-white dark:bg-zinc-800 rounded-xl border border-gray-200 dark:border-zinc-700 overflow-hidden">
          <button
            onClick={() => {
              setShowAdvancedSettings(!showAdvancedSettings);
              if (!showAdvancedSettings) {
                setStorageInfo(getStorageInfo());
              }
            }}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-zinc-700/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="font-medium text-gray-900 dark:text-white">Pengaturan Lanjutan</span>
            </div>
            <svg 
              className={`w-5 h-5 text-gray-400 transition-transform ${showAdvancedSettings ? 'rotate-180' : ''}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showAdvancedSettings && (
            <div className="px-6 py-4 border-t border-gray-200 dark:border-zinc-700 space-y-4">
              {/* Storage Info */}
              {storageInfo && storageInfo.available && (
                <div className="bg-gray-50 dark:bg-zinc-900/50 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Storage Info</h4>
                  <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                    <div>Keys: <span className="font-mono">{storageInfo.keyCount}</span></div>
                    <div>Size: <span className="font-mono">{storageInfo.totalSizeKB} KB</span></div>
                    <div>Version: <span className="font-mono">{storageInfo.version}</span></div>
                  </div>
                </div>
              )}

              {/* Emergency Cleanup */}
              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-red-900 dark:text-red-300 mb-1">Emergency Cleanup</h4>
                    <p className="text-xs text-red-700 dark:text-red-400 mb-3">
                      Gunakan ini jika aplikasi tidak berfungsi dengan baik. Akan membersihkan semua data lokal (kecuali theme) dan reload halaman.
                    </p>
                    <button
                      onClick={() => {
                        if (window.confirm('⚠️ PERINGATAN!\n\nIni akan:\n• Menghapus semua data lokal\n• Logout otomatis\n• Reload halaman\n\nLanjutkan?')) {
                          emergencyCleanup();
                        }
                      }}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      Emergency Cleanup
                    </button>
                  </div>
                </div>
              </div>

              {/* Helpful Info */}
              <div className="text-xs text-gray-500 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <strong className="text-blue-900 dark:text-blue-300">Tips:</strong>
                    <p className="mt-1">Aplikasi secara otomatis membersihkan data lama saat dimulai. Emergency cleanup hanya diperlukan jika aplikasi tidak berfungsi sama sekali.</p>
                  </div>
                </div>
              </div>
            </div>
          )}
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
