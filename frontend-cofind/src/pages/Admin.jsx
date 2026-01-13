import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/authContext';
import { supabase } from '../lib/supabase';
import { Link } from 'react-router-dom';

const Admin = () => {
  const { profile, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalReviews: 0,
    totalReports: 0,
    pendingReports: 0
  });
  const [recentReviews, setRecentReviews] = useState([]);
  const [recentReports, setRecentReports] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard', 'reviews', 'reports', 'users'

  useEffect(() => {
    if (isAdmin) {
      loadDashboardData();
    }
  }, [isAdmin]);

  const loadDashboardData = async () => {
    if (!supabase) return;
    setLoading(true);

    try {
      // Get stats
      const [usersCount, reviewsCount, reportsCount, pendingReportsCount] = await Promise.all([
        supabase.from('profiles').select('*', { count: 'exact', head: true }),
        supabase.from('reviews').select('*', { count: 'exact', head: true }),
        supabase.from('review_reports').select('*', { count: 'exact', head: true }),
        supabase.from('review_reports').select('*', { count: 'exact', head: true }).eq('status', 'pending')
      ]);

      setStats({
        totalUsers: usersCount.count || 0,
        totalReviews: reviewsCount.count || 0,
        totalReports: reportsCount.count || 0,
        pendingReports: pendingReportsCount.count || 0
      });

      // Get recent reviews
      const { data: reviews } = await supabase
        .from('reviews')
        .select(`
          *,
          profiles:user_id (username, avatar_url),
          place_id
        `)
        .order('created_at', { ascending: false })
        .limit(10);

      setRecentReviews(reviews || []);

      // Get recent reports
      const { data: reports } = await supabase
        .from('review_reports')
        .select(`
          *,
          reviews:review_id (text, place_id),
          profiles:reporter_id (username)
        `)
        .order('created_at', { ascending: false })
        .limit(10);

      setRecentReports(reports || []);

    } catch (err) {
      console.error('Error loading dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReportAction = async (reportId, action) => {
    if (!supabase) return;

    try {
      const { error } = await supabase
        .from('review_reports')
        .update({ status: action })
        .eq('id', reportId);

      if (!error) {
        await loadDashboardData();
      }
    } catch (err) {
      console.error('Error updating report:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600"></div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-800 rounded-2xl shadow-xl p-8 text-center">
          <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Akses Ditolak
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Halaman ini hanya dapat diakses oleh administrator.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
          >
            Kembali ke Beranda
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <Link 
            to="/" 
            className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-amber-600 dark:hover:text-amber-500 text-sm mb-4"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Kembali ke Beranda
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Admin Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">Selamat datang, {profile?.username || 'Admin'}!</p>
        </div>

        {/* Tabs */}
        <div className="mb-6 border-b border-gray-200 dark:border-zinc-700">
          <div className="flex gap-4">
            {[
              { id: 'dashboard', label: 'Dashboard' },
              { id: 'reviews', label: 'Reviews' },
              { id: 'reports', label: 'Reports' },
              { id: 'users', label: 'Users' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-amber-500 text-amber-600 dark:text-amber-400'
                    : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Total Users</p>
                    <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{stats.totalUsers}</p>
                  </div>
                  <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Total Reviews</p>
                    <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{stats.totalReviews}</p>
                  </div>
                  <div className="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                    </svg>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Total Reports</p>
                    <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{stats.totalReports}</p>
                  </div>
                  <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Pending Reports</p>
                    <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{stats.pendingReports}</p>
                  </div>
                  <div className="w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* Recent Reviews */}
            <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Recent Reviews</h2>
              <div className="space-y-4">
                {recentReviews.length > 0 ? (
                  recentReviews.map(review => (
                    <div key={review.id} className="border-b border-gray-200 dark:border-zinc-700 pb-4 last:border-b-0">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="font-semibold text-gray-900 dark:text-white">
                              {review.profiles?.username || 'Unknown'}
                            </span>
                            <span className="text-sm text-gray-500 dark:text-gray-400">
                              {new Date(review.created_at).toLocaleDateString('id-ID')}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">{review.text}</p>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500 dark:text-gray-400">Place ID:</span>
                            <span className="text-xs font-mono text-gray-600 dark:text-gray-400">{review.place_id}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {[1, 2, 3, 4, 5].map(star => (
                            <svg
                              key={star}
                              className={`w-4 h-4 ${
                                star <= review.rating
                                  ? 'text-amber-400 fill-current'
                                  : 'text-gray-300 dark:text-zinc-600'
                              }`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                              />
                            </svg>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500 dark:text-gray-400 text-center py-8">Belum ada review</p>
                )}
              </div>
            </div>

            {/* Recent Reports */}
            <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Recent Reports</h2>
              <div className="space-y-4">
                {recentReports.length > 0 ? (
                  recentReports.map(report => (
                    <div key={report.id} className="border-b border-gray-200 dark:border-zinc-700 pb-4 last:border-b-0">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="font-semibold text-gray-900 dark:text-white">
                              Reported by: {report.profiles?.username || 'Unknown'}
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              report.status === 'pending'
                                ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                                : report.status === 'reviewed'
                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                                : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                            }`}>
                              {report.status}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">{report.reason}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Review: {report.reviews?.text?.substring(0, 100) || 'N/A'}...
                          </p>
                        </div>
                        {report.status === 'pending' && (
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleReportAction(report.id, 'reviewed')}
                              className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleReportAction(report.id, 'dismissed')}
                              className="px-3 py-1.5 bg-gray-600 text-white text-sm rounded-lg hover:bg-gray-700"
                            >
                              Dismiss
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500 dark:text-gray-400 text-center py-8">Belum ada laporan</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Reviews Tab */}
        {activeTab === 'reviews' && (
          <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">All Reviews</h2>
            <p className="text-gray-500 dark:text-gray-400">Fitur ini akan dikembangkan lebih lanjut...</p>
          </div>
        )}

        {/* Reports Tab */}
        {activeTab === 'reports' && (
          <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">All Reports</h2>
            <p className="text-gray-500 dark:text-gray-400">Fitur ini akan dikembangkan lebih lanjut...</p>
          </div>
        )}

        {/* Users Tab */}
        {activeTab === 'users' && (
          <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 border border-gray-200 dark:border-zinc-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">All Users</h2>
            <p className="text-gray-500 dark:text-gray-400">Fitur ini akan dikembangkan lebih lanjut...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Admin;
