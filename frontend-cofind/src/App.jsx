// src/App.jsx
import React, { useEffect, lazy, Suspense } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/authContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import { initializeSessionFix } from './utils/sessionFix';
// import './utils/debugSessionIssue'; // Temporarily disabled - will import manually when needed

// Lazy load page components for code splitting
// This reduces initial bundle size and improves FCP/LCP
const ShopList = lazy(() => import('./pages/ShopList'));
const ShopDetail = lazy(() => import('./pages/ShopDetail'));
const Favorite = lazy(() => import('./pages/Favorite'));
const WantToVisit = lazy(() => import('./pages/WantToVisit'));
const About = lazy(() => import('./pages/About'));
const Login = lazy(() => import('./pages/Login'));
const Profile = lazy(() => import('./pages/Profile'));
const Admin = lazy(() => import('./pages/Admin'));

// Photo tools removed (local images only)

/**
 * Loading fallback component - ditampilkan saat page sedang di-load
 * Minimal styling untuk tidak menambah weight
 */
function PageLoadingFallback() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading...</p>
      </div>
    </div>
  );
}

function AppContent() {
  const location = useLocation();
  const isLoginPage = location.pathname === '/login';

  return (
    <div 
      className={`${isLoginPage ? 'fixed inset-0 overflow-hidden' : 'min-h-screen'} bg-gray-50 dark:bg-zinc-900 w-full`}
      style={isLoginPage ? { width: '100vw', height: '100vh', minHeight: '100vh' } : {}}
    >
      {/* 1. Navbar (fixed di atas) - Hidden di login page */}
      {!isLoginPage && <Navbar />}
      
      {/* 2. Main Content (padding untuk menghindari navbar, kecuali di login) */}
      <main 
        className={isLoginPage ? 'w-full' : 'pt-14 sm:pt-16 w-full'}
        style={isLoginPage ? { width: '100vw', height: '100vh', minHeight: '100vh' } : {}}
      > 
        <Routes>
          <Route path="/" element={<Suspense fallback={<PageLoadingFallback />}><ShopList /></Suspense>} /> 
          <Route path="/shop/:id" element={<Suspense fallback={<PageLoadingFallback />}><ShopDetail /></Suspense>} />
          <Route path="/favorite" element={<Suspense fallback={<PageLoadingFallback />}><Favorite /></Suspense>} />
          <Route path="/want-to-visit" element={<Suspense fallback={<PageLoadingFallback />}><WantToVisit /></Suspense>} />
          <Route path="/about" element={<Suspense fallback={<PageLoadingFallback />}><About /></Suspense>} />
          <Route path="/login" element={<Suspense fallback={<PageLoadingFallback />}><Login /></Suspense>} />
          {/* Profil publik: bisa diakses siapa saja */}
          <Route path="/profile/:userId" element={<Suspense fallback={<PageLoadingFallback />}><Profile /></Suspense>} />
          {/* Profil saya: butuh login */}
          <Route 
            path="/profile" 
            element={
              <ProtectedRoute>
                <Suspense fallback={<PageLoadingFallback />}>
                  <Profile />
                </Suspense>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin" 
            element={
              <AdminRoute>
                <Suspense fallback={<PageLoadingFallback />}>
                  <Admin />
                </Suspense>
              </AdminRoute>
            } 
          />
        </Routes>
      </main>
      
      {/* 3. Footer (di bawah) - Hidden di login page */}
      {!isLoginPage && <Footer />}
    </div>
  );
}

function App() {
  // Initialize session fix on app load
  useEffect(() => {
    initializeSessionFix();
  }, []);

  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;