// src/App.jsx
import React, { useEffect, lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/authContext';
import { useAuth } from './context/authContext';
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

/**
 * Guard untuk halaman user biasa: jika admin, redirect ke /admin
 */
function UserRoute({ children }) {
  const { isAdmin, initialized, loading } = useAuth();
  if (!initialized || loading) return null;
  if (isAdmin) return <Navigate to="/admin" replace />;
  return children;
}

function AppContent() {
  const location = useLocation();
  const { isAdmin } = useAuth();

  const isLoginPage = location.pathname === '/login';
  const isAdminPage = location.pathname.startsWith('/admin');
  // Sembunyikan Navbar/Footer di halaman login dan di semua halaman untuk admin
  const hideChrome = isLoginPage || isAdminPage || isAdmin;

  return (
    <div 
      className={`${isLoginPage ? 'fixed inset-0 overflow-hidden' : 'min-h-screen'} bg-gray-50 dark:bg-zinc-900 w-full`}
      style={isLoginPage ? { width: '100vw', height: '100vh', minHeight: '100vh' } : {}}
    >
      {/* Navbar - disembunyikan di login & untuk admin */}
      {!hideChrome && <Navbar />}
      
      <main 
        className={isLoginPage ? 'w-full' : hideChrome ? 'w-full' : 'pt-14 sm:pt-16 w-full'}
        style={isLoginPage ? { width: '100vw', height: '100vh', minHeight: '100vh' } : {}}
      > 
        <Routes>
          {/* Halaman user biasa — admin akan di-redirect ke /admin */}
          <Route path="/" element={<UserRoute><Suspense fallback={<PageLoadingFallback />}><ShopList /></Suspense></UserRoute>} /> 
          <Route path="/shop/:id" element={<UserRoute><Suspense fallback={<PageLoadingFallback />}><ShopDetail /></Suspense></UserRoute>} />
          <Route path="/favorite" element={<UserRoute><Suspense fallback={<PageLoadingFallback />}><Favorite /></Suspense></UserRoute>} />
          <Route path="/want-to-visit" element={<UserRoute><Suspense fallback={<PageLoadingFallback />}><WantToVisit /></Suspense></UserRoute>} />
          <Route path="/about" element={<UserRoute><Suspense fallback={<PageLoadingFallback />}><About /></Suspense></UserRoute>} />
          <Route path="/login" element={<Suspense fallback={<PageLoadingFallback />}><Login /></Suspense>} />
          <Route path="/profile/:userId" element={<UserRoute><Suspense fallback={<PageLoadingFallback />}><Profile /></Suspense></UserRoute>} />
          <Route 
            path="/profile" 
            element={
              <UserRoute>
                <ProtectedRoute>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <Profile />
                  </Suspense>
                </ProtectedRoute>
              </UserRoute>
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
      
      {/* Footer - disembunyikan di login & untuk admin */}
      {!hideChrome && <Footer />}
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