import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';
import coffeeshopBg from '../assets/sign_page.webp';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn, signUp, resetPassword, isAuthenticated, isAdmin, loading } = useAuth();
  
  const [mode, setMode] = useState('login'); // 'login', 'register', 'forgot'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Title halaman
  useEffect(() => {
    document.title = 'Masuk - Cofind';
    return () => { document.title = 'Cofind'; };
  }, []);

  // Redirect if already logged in
  useEffect(() => {
    console.log('[Login] isAuthenticated changed:', isAuthenticated, 'isSubmitting:', isSubmitting);
  }, [isAuthenticated]);

  useEffect(() => {
    console.log('[Login] isSubmitting changed:', isSubmitting);
  }, [isSubmitting]);

  useEffect(() => {
    console.log('[Login] useEffect check:', { isAuthenticated, isAdmin, isSubmitting, location: location.state });
    if (isAuthenticated && !isSubmitting) {
      // Admin selalu diarahkan ke /admin
      if (isAdmin) {
        navigate('/admin', { replace: true });
        return;
      }

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
  }, [isAuthenticated, isAdmin, navigate, location, isSubmitting]);

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
          console.error('[Login] Sign in error:', error);
          setError(error.message);
          setIsSubmitting(false);
        } else {
          // Success - redirect will be handled by useEffect with debounce
          console.log('[Login] Sign in successful, setting success message');
          setSuccess('Login berhasil! Mengarahkan...');
          // Don't set isSubmitting to false - let the redirect handle it
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
        if (password.length < 8) {
          setError('Password minimal 8 karakter.');
          setIsSubmitting(false);
          return;
        }

        const { error } = await signUp(username.trim(), password, fullName.trim());

        if (error) {
          setError(error.message || 'Gagal mendaftar. Silakan coba lagi.');
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
            setIsSubmitting(false);
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
      <div className="flex min-h-screen w-full items-center justify-center bg-cofind-background">
        <div className="h-12 w-12 animate-spin rounded-full border-2 border-cofind-rule border-t-cofind-primary" />
      </div>
    );
  }

  const modeTitle =
    mode === 'login' ? 'Sign in' : mode === 'register' ? 'Sign up' : 'Reset password';

  const submitLabel =
    mode === 'login' ? 'Sign in now' : mode === 'register' ? 'Sign up now' : 'Send Reset Link';

  return (
    <div className="flex min-h-screen w-full flex-col bg-cofind-background lg:flex-row">
      <div className="relative flex w-full flex-1 flex-col lg:w-1/2 lg:min-h-screen">
        <div className="flex items-center justify-between px-4 py-4 sm:px-6 lg:px-10">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-cofind-secondary transition-colors hover:text-cofind-primary"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Kembali ke Beranda
          </Link>
          <Link to="/" className="font-display text-xl font-bold text-cofind-ink lg:hidden">
            CoFind
          </Link>
        </div>

        <div className="flex flex-1 items-start justify-center px-4 pb-10 pt-2 sm:px-6 lg:px-10 lg:pb-12 lg:pt-6">
          <div className="w-full max-w-md">
            <div className="rounded-panel border border-cofind-rule bg-cofind-surface p-6 shadow-cofind-md sm:p-8 lg:p-10">
              <h2 className="mb-8 font-display text-3xl font-bold text-cofind-ink">{modeTitle}</h2>

              {error ? (
                <div
                  data-testid="login-error"
                  className="mb-4 rounded-control border border-red-200 bg-red-50 p-3"
                >
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              ) : null}
              {success ? (
                <div
                  data-testid="login-success"
                  className="mb-4 rounded-control border border-emerald-200 bg-emerald-50 p-3"
                >
                  <p className="text-sm text-emerald-900">{success}</p>
                </div>
              ) : null}

              <form data-testid="login-form" onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="login-username" className="mb-2 block text-sm font-medium text-cofind-ink">
                    Username
                  </label>
                  <Input
                    id="login-username"
                    data-testid="login-username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder={mode === 'login' ? 'Masukkan username Anda' : 'Pilih username (min 3 karakter)'}
                    required
                    minLength={mode === 'register' ? 3 : undefined}
                  />
                </div>

                {mode === 'register' ? (
                  <div>
                    <label htmlFor="register-fullname" className="mb-2 block text-sm font-medium text-cofind-ink">
                      Nama Lengkap (Opsional)
                    </label>
                    <Input
                      id="register-fullname"
                      data-testid="register-fullname"
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Nama Lengkap Anda"
                    />
                  </div>
                ) : null}

                {mode !== 'forgot' ? (
                  <div>
                    <label htmlFor="login-password" className="mb-2 block text-sm font-medium text-cofind-ink">
                      Password
                    </label>
                    <Input
                      id="login-password"
                      data-testid="login-password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Kata Sandi"
                      required
                      minLength={mode === 'register' ? 8 : undefined}
                    />
                  </div>
                ) : null}

                {mode === 'register' ? (
                  <div>
                    <label htmlFor="register-confirm-password" className="mb-2 block text-sm font-medium text-cofind-ink">
                      Konfirmasi Password
                    </label>
                    <Input
                      id="register-confirm-password"
                      data-testid="register-confirm-password"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      minLength={8}
                    />
                  </div>
                ) : null}

                <Button
                  data-testid="login-submit"
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full"
                  size="lg"
                >
                  {isSubmitting ? (
                    <>
                      <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-cofind-on-primary/30 border-t-cofind-on-primary" />
                      <span>Memproses...</span>
                    </>
                  ) : (
                    submitLabel
                  )}
                </Button>
              </form>

              <div className="mt-6 text-center text-sm text-cofind-muted">
                {mode === 'login' ? (
                  <>
                    Belum punya akun?{' '}
                    <button
                      type="button"
                      data-testid="login-switch-register"
                      onClick={() => {
                        setMode('register');
                        setError('');
                        setSuccess('');
                      }}
                      className="font-semibold text-cofind-secondary underline underline-offset-2 transition-colors hover:text-cofind-primary"
                    >
                      Daftar sekarang
                    </button>
                  </>
                ) : null}
                {mode === 'register' ? (
                  <>
                    Sudah punya akun?{' '}
                    <button
                      type="button"
                      onClick={() => {
                        setMode('login');
                        setError('');
                        setSuccess('');
                      }}
                      className="font-semibold text-cofind-secondary underline underline-offset-2 transition-colors hover:text-cofind-primary"
                    >
                      Masuk di sini
                    </button>
                  </>
                ) : null}
                {mode === 'forgot' ? (
                  <>
                    Ingat password?{' '}
                    <button
                      type="button"
                      onClick={() => {
                        setMode('login');
                        setError('');
                        setSuccess('');
                      }}
                      className="font-semibold text-cofind-secondary underline underline-offset-2 transition-colors hover:text-cofind-primary"
                    >
                      Kembali ke login
                    </button>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        className="relative hidden min-h-screen w-full bg-cofind-ink lg:block lg:w-1/2"
        style={{
          backgroundImage: `url(${coffeeshopBg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-cofind-ink/55" aria-hidden />
        <div className="relative z-10 flex h-full min-h-screen flex-col justify-between p-10 text-cofind-paper xl:p-12">
          <div>
            <p className="font-display text-sm font-semibold uppercase tracking-wide text-cofind-paper/80">
              Cofind
            </p>
            <h2 className="mt-4 font-display text-5xl font-bold leading-tight">
              Welcome,
              <br />
              Coffee Hunter!
            </h2>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-cofind-paper/85">
              Temukan coffee shop terbaik di sekitar Anda. Bergabunglah dengan komunitas pecinta kopi
              dan bagikan pengalaman Anda.
            </p>
          </div>
          <div>
            <div className="flex gap-4">
                <a
                  href="https://www.tiktok.com/@vaegerys?_r=1&_t=ZS-93fKQupQptJ"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
                  aria-label="TikTok"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
                  </svg>
                </a>
                <a
                  href="https://www.instagram.com/mohammadfulvi?igsh=NXVhY3k1bXlnMzJr"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
                  aria-label="Instagram"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                </a>
                <a
                  href="https://www.facebook.com/share/184FAdjGpV/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-full border-2 border-white/30 flex items-center justify-center hover:border-white/60 transition-colors"
                  aria-label="Facebook"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </a>
                <a
                  href="https://youtube.com/@mohammadanandafulvi5058?si=iYPVlvu8crQAvej0"
                  target="_blank"
                  rel="noopener noreferrer"
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
  );
};

export default Login;
