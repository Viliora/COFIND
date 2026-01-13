import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/authContext';

const AdminRoute = ({ children }) => {
  const { isAuthenticated, isAdmin, loading, initialized, isSupabaseConfigured } = useAuth();
  const location = useLocation();

  // Show loading while checking auth
  if (!initialized || loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Memeriksa autentikasi...</p>
        </div>
      </div>
    );
  }

  // If Supabase not configured, show warning
  if (!isSupabaseConfigured) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-800 rounded-2xl shadow-xl p-8 text-center">
          <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Login Diperlukan
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Fitur ini memerlukan Supabase yang belum dikonfigurasi.
          </p>
        </div>
      </div>
    );
  }

  // If not authenticated, redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If not admin, show access denied (Admin page will handle this, but this is extra protection)
  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return children;
};

export default AdminRoute;
