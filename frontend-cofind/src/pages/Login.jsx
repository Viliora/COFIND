import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import coffeeshopBg from '../assets/coffeeshop_2.jpg';

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn, signUp, resetPassword, isAuthenticated, isSupabaseConfigured, loading } = useAuth();
  
  const [mode, setMode] = useState('login'); // 'login', 'register', 'forgot'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if already logged in
  useEffect(() => {
    if (isAuthenticated && !isSubmitting) {
      // Check if there's redirect info from ReviewForm
      const redirectState = location.state;
      let redirectPath = '/';
      let scrollToReview = false;
      let placeId = null;
      
      // Handle different state formats
      if (redirectState?.from?.pathname) {
        redirectPath = redirectState.from.pathname;
        scrollToReview = redirectState.scrollToReview || redirectState.from.search?.includes('scrollToReview');
        placeId = redirectState.placeId;
      } else if (redirectState?.from && typeof redirectState.from === 'string') {
        redirectPath = redirectState.from;
        scrollToReview = redirectState.scrollToReview;
        placeId = redirectState.placeId;
      } else if (redirectState?.placeId) {
        // Direct placeId provided
        redirectPath = `/shop/${redirectState.placeId}`;
        scrollToReview = redirectState.scrollToReview || true;
        placeId = redirectState.placeId;
      }
      
      console.log('[Login] Redirecting after login:', { redirectPath, scrollToReview, placeId });
      
      // Navigate to the target page with scroll state
      if (redirectPath && redirectPath !== '/') {
        navigate(redirectPath, { 
          replace: true,
          state: {
            scrollToReview: scrollToReview,
            placeId: placeId
          }
        });
      } else {
        navigate('/', { replace: true });
      }
    }
  }, [isAuthenticated, navigate, location, isSubmitting]);

  // Show warning if Supabase not configured
  if (!isSupabaseConfigured) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-800 rounded-2xl shadow-xl p-8 text-center">
          <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Supabase Belum Dikonfigurasi
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Fitur login memerlukan konfigurasi Supabase. Silakan tambahkan VITE_SUPABASE_URL dan VITE_SUPABASE_ANON_KEY di file .env
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Kembali ke Beranda
          </Link>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsSubmitting(true);

    try {
      if (mode === 'login') {
        if (!username.trim()) {
          setError('Username wajib diisi');
          setIsSubmitting(false);
          return;
        }
        
        const { error } = await signIn(username.trim(), password);
        if (error) {
          setError(error.message);
        } else {
          // Success - redirect will be handled by useEffect
          setSuccess('Login berhasil! Mengarahkan...');
        }
      } else if (mode === 'register') {
        if (!username.trim()) {
          setError('Username wajib diisi');
          setIsSubmitting(false);
          return;
        }
        if (username.trim().length < 3) {
          setError('Username minimal 3 karakter');
          setIsSubmitting(false);
          return;
        }
        if (password !== confirmPassword) {
          setError('Password tidak cocok');
          setIsSubmitting(false);
          return;
        }
        // Enhanced password validation
        if (password.length < 8) {
          setError('Password minimal 8 karakter. Untuk keamanan lebih baik, gunakan minimal 12 karakter dengan kombinasi huruf besar, huruf kecil, angka, dan karakter khusus.');
          setIsSubmitting(false);
          return;
        }
        
        // Additional password strength checks (optional but recommended)
        if (password.length < 12) {
          // Warn but don't block - allow 8-11 chars but suggest stronger
          console.warn('[Login] Password kurang dari 12 karakter - disarankan menggunakan password yang lebih kuat');
        }

        const { error } = await signUp(username.trim(), password, {
          full_name: fullName.trim()
        });

        if (error) {
          // Handle leaked password error specifically (jika Leaked Password Protection enabled)
          const errorMsg = error.message?.toLowerCase() || '';
          if (errorMsg.includes('breach') || 
              errorMsg.includes('pwned') || 
              errorMsg.includes('compromised') || 
              errorMsg.includes('leaked') ||
              errorMsg.includes('data breach')) {
            setError('Password ini telah ditemukan dalam data breach. Silakan pilih password yang berbeda dan lebih kuat untuk keamanan akun Anda.');
          } else if (errorMsg.includes('password') && errorMsg.includes('weak')) {
            setError('Password terlalu lemah. Gunakan password minimal 12 karakter dengan kombinasi huruf besar, huruf kecil, angka, dan karakter khusus.');
          } else {
            setError(error.message || 'Gagal mendaftar. Silakan coba lagi.');
          }
        } else {
          // After successful signup, auto-login
          const { error: loginError } = await signIn(username.trim(), password);
          if (loginError) {
            setSuccess('Registrasi berhasil! Silakan login dengan username Anda.');
            setMode('login');
            setUsername('');
            setPassword('');
            setConfirmPassword('');
            setFullName('');
          } else {
            // Auto-login successful - redirect will be handled by useEffect
            setSuccess('Registrasi dan login berhasil! Mengarahkan...');
          }
        }
      } else if (mode === 'forgot') {
        if (!username.trim()) {
          setError('Username wajib diisi');
          setIsSubmitting(false);
          return;
        }
        
        const { error } = await resetPassword(username.trim());
        if (error) {
          setError(error.message);
        } else {
          setSuccess('Link reset password telah dikirim. Silakan cek email Anda.');
        }
      }
    } catch {
      setError('Terjadi kesalahan. Silakan coba lagi.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600"></div>
      </div>
    );
  }

  return (
    <div 
      className="fixed inset-0 flex relative"
      style={{
        backgroundImage: `url(${coffeeshopBg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        backgroundAttachment: 'fixed',
        width: '100vw',
        height: '100vh',
        minHeight: '100vh'
      }}
    >
      {/* Dark Overlay */}
      <div 
        className="absolute inset-0 bg-black/60" 
        style={{ 
          width: '100vw', 
          height: '100vh',
          minHeight: '100vh',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0
        }}
      ></div>

      {/* Back to Home Button - Top Right */}
      <Link
        to="/"
        className="absolute top-6 right-6 z-20 flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-md text-white rounded-lg border border-white/20 hover:bg-white/20 transition-all duration-200 shadow-lg"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        <span className="font-medium">Kembali ke Beranda</span>
      </Link>

      {/* Content Container */}
      <div 
        className="relative z-10 w-full flex"
        style={{ 
          height: '100vh',
          minHeight: '100vh'
        }}
      >
        {/* Left Section - Sign In Form */}
        <div 
          className="w-full lg:w-1/2 flex items-start justify-center p-8 lg:p-12"
          style={{ height: '100vh', minHeight: '100vh' }}
        >
          <div className="w-full max-w-md pt-8 lg:pt-12">
            {/* Mobile Logo */}
            <div className="lg:hidden text-center mb-8">
              <Link to="/" className="inline-block">
                <h1 className="text-3xl font-bold text-white">CoFind</h1>
              </Link>
            </div>

            {/* Form Card */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-8 lg:p-10 border border-white/20 shadow-2xl">
              <h2 className="text-3xl font-bold text-white mb-8">
                {mode === 'login' && 'Sign in'}
                {mode === 'register' && 'Sign up'}
                {mode === 'forgot' && 'Reset password'}
              </h2>

              {/* Error/Success Messages */}
              {error && (
                <div className="mb-4 p-3 bg-red-500/20 border border-red-400/50 rounded-lg backdrop-blur-sm">
                  <p className="text-sm text-red-100">{error}</p>
                </div>
              )}
              {success && (
                <div className="mb-4 p-3 bg-green-500/20 border border-green-400/50 rounded-lg backdrop-blur-sm">
                  <p className="text-sm text-green-100">{success}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Username */}
                <div>
                  <label className="block text-sm font-medium text-white mb-2">
                    Username
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full px-4 py-3 bg-white/90 text-gray-900 rounded-lg border border-white/30 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all"
                    placeholder={mode === 'login' ? 'Masukkan username Anda' : 'Pilih username (min 3 karakter)'}
                    required
                    minLength={mode === 'register' ? 3 : undefined}
                  />
                </div>

                {/* Full Name (only for register) */}
                {mode === 'register' && (
                  <div>
                    <label className="block text-sm font-medium text-white mb-2">
                      Nama Lengkap (Opsional)
                    </label>
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full px-4 py-3 bg-white/90 text-gray-900 rounded-lg border border-white/30 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all"
                      placeholder="Nama Lengkap Anda"
                    />
                  </div>
                )}

                {/* Password */}
                {mode !== 'forgot' && (
                  <div>
                    <label className="block text-sm font-medium text-white mb-2">
                      Password
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full px-4 py-3 bg-white/90 text-gray-900 rounded-lg border border-white/30 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all"
                      placeholder="••••••••"
                      required
                      minLength={6}
                    />
                  </div>
                )}

                {/* Confirm Password (only for register) */}
                {mode === 'register' && (
                  <div>
                    <label className="block text-sm font-medium text-white mb-2">
                      Konfirmasi Password
                    </label>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full px-4 py-3 bg-white/90 text-gray-900 rounded-lg border border-white/30 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all"
                      placeholder="••••••••"
                      required
                      minLength={6}
                    />
                  </div>
                )}

                {/* Remember Me & Forgot Password (only for login) */}
                {mode === 'login' && (
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                        className="w-4 h-4 rounded border-white/30 bg-white/20 text-orange-500 focus:ring-2 focus:ring-orange-500 focus:ring-offset-0"
                      />
                      <span className="text-sm text-white">Remember Me</span>
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setMode('forgot');
                        setError('');
                        setSuccess('');
                      }}
                      className="text-sm text-white hover:text-orange-400 transition-colors"
                    >
                      Lost your password?
                    </button>
                  </div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3.5 px-4 bg-orange-500 hover:bg-orange-600 disabled:bg-orange-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg hover:shadow-xl disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                      <span>Memproses...</span>
                    </>
                  ) : (
                    <>
                      {mode === 'login' && 'Sign in now'}
                      {mode === 'register' && 'Sign up now'}
                      {mode === 'forgot' && 'Send Reset Link'}
                    </>
                  )}
                </button>
              </form>

              {/* Mode Switcher */}
              <div className="mt-6 text-center text-sm text-white/80">
                {mode === 'login' && (
                  <>
                    Belum punya akun?{' '}
                    <button
                      onClick={() => {
                        setMode('register');
                        setError('');
                        setSuccess('');
                      }}
                      className="text-white hover:text-orange-400 font-medium transition-colors"
                    >
                      Daftar sekarang
                    </button>
                  </>
                )}
                {mode === 'register' && (
                  <>
                    Sudah punya akun?{' '}
                    <button
                      onClick={() => {
                        setMode('login');
                        setError('');
                        setSuccess('');
                      }}
                      className="text-white hover:text-orange-400 font-medium transition-colors"
                    >
                      Masuk di sini
                    </button>
                  </>
                )}
                {mode === 'forgot' && (
                  <>
                    Ingat password?{' '}
                    <button
                      onClick={() => {
                        setMode('login');
                        setError('');
                        setSuccess('');
                      }}
                      className="text-white hover:text-orange-400 font-medium transition-colors"
                    >
                      Kembali ke login
                    </button>
                  </>
                )}
              </div>

              {/* Terms & Privacy */}
              <div className="mt-6 text-center text-xs text-white/60">
                By clicking on '{mode === 'login' ? 'Sign in now' : mode === 'register' ? 'Sign up now' : 'Send Reset Link'}' you agree to{' '}
                <a href="#" className="underline hover:text-white transition-colors">Terms of Service</a>
                {' '}|{' '}
                <a href="#" className="underline hover:text-white transition-colors">Privacy Policy</a>
              </div>
            </div>
          </div>
        </div>

        {/* Right Section - Welcome Message */}
        <div 
          className="hidden lg:flex lg:w-1/2 items-start p-12 text-white"
          style={{ height: '100vh', minHeight: '100vh' }}
        >
          {/* Wrapper div untuk alignment dengan card - menggunakan flexbox yang sama dengan left section */}
          <div className="flex flex-col w-full h-full justify-between pt-8 lg:pt-12">
            {/* Top section - sejajar dengan card */}
            <div className="flex-shrink-0">
              <h2 className="text-5xl font-bold mb-6 leading-tight">
                Welcome,
                <br />
                Coffee Hunter!
              </h2>
              
              <p className="text-lg text-white/80 leading-relaxed max-w-md">
                Temukan coffee shop terbaik di sekitar Anda. Bergabunglah dengan komunitas pecinta kopi dan bagikan pengalaman Anda.
              </p>
            </div>
            
            {/* Bottom section - social icons */}
            <div className="flex-shrink-0">
              <div className="flex gap-4">
            <a 
              href="#" 
              className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
              aria-label="Facebook"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
              </svg>
            </a>
            <a 
              href="#" 
              className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
              aria-label="Twitter"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
              </svg>
            </a>
            <a 
              href="#" 
              className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
              aria-label="Instagram"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
              </svg>
            </a>
            <a 
              href="#" 
              className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
              aria-label="YouTube"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
