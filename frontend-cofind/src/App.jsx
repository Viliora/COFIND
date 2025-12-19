// src/App.jsx
import React from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ShopList from './pages/ShopList';
import ShopDetail from './pages/ShopDetail';
import Favorite from './pages/Favorite';
import WantToVisit from './pages/WantToVisit';
import About from './pages/About';
import Login from './pages/Login';
import Profile from './pages/Profile';
import Admin from './pages/Admin';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';

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
          <Route path="/" element={<ShopList />} /> 
          <Route path="/shop/:id" element={<ShopDetail />} />
          <Route path="/favorite" element={<Favorite />} />
          <Route path="/want-to-visit" element={<WantToVisit />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route 
            path="/profile" 
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin" 
            element={
              <AdminRoute>
                <Admin />
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
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;