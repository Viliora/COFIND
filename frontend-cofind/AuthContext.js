import React, {
    createContext,
    useContext,
    useEffect,
    useState,
    useRef,
    useCallback,
    useMemo,
  } from "react";
  
  import { supabase, isSupabaseConfigured, getUserProfile } from "../lib/supabase";
  import { migrateLocalStorageToSupabase } from "../utils/migrateFavorites";
  
  // import { useAuth } from "../context/AuthContext";
  
  /**
   * AUTH CONTEXT — FINAL (lebih tahan refresh / alt-tab / token refresh)
   *
   * Fokus perbaikan:
   * 1) Tidak “drop” event auth saat sedang processing (pakai pending event queue).
   * 2) Init auth selalu mengakhiri loading & initialized dengan guard attempt.
   * 3) Fetch profile aman (race-safe) + tidak update state jika unmounted.
   * 4) Optional: re-sync saat tab kembali aktif (visibilitychange).
   */
  
  const AuthContext = createContext(null);
  
  function useAuth() {
    const ctx = useContext(AuthContext);
    if (ctx === null) {
      throw new Error("useAuth must be used within an AuthProvider");
    }
    return ctx;
  }
  
  function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [initialized, setInitialized] = useState(false);
  
    // Refs untuk mencegah race condition
    const isMountedRef = useRef(true);
    const initAttemptRef = useRef(0);
    const currentUserIdRef = useRef(null);
  
    // Cegah “double processing” tapi jangan drop event -> queue 1 event terakhir
    const isProcessingRef = useRef(false);
    const pendingAuthEventRef = useRef(null);
  
    // (Opsional) Guard untuk fetchProfile agar result lama tidak menimpa state terbaru
    const profileFetchSeqRef = useRef(0);
  
    const usernameToEmail = useCallback((username) => {
      // Sesuaikan dengan pola project kamu. Aman: domain dari env (atau fallback).
      const domain = import.meta.env.VITE_AUTH_EMAIL_DOMAIN || "cofind.local";
      const normalized = String(username || "")
        .toLowerCase()
        .trim()
        .replace(/\s+/g, "");
      if (!normalized) return "";
      // Jika sudah email, pakai apa adanya
      if (normalized.includes("@")) return normalized;
      return `${normalized}@${domain}`;
    }, []);
  
    const setUserSafe = useCallback((newUser) => {
      if (!isMountedRef.current) return;
      currentUserIdRef.current = newUser?.id || null;
      setUser(newUser || null);
    }, []);
  
    const fetchProfile = useCallback(async (userId) => {
      if (!supabase || !userId) return null;
  
      const seq = ++profileFetchSeqRef.current;
  
      try {
        const profileData = await getUserProfile(userId);
  
        // Kalau ada fetch lebih baru, abaikan hasil ini
        if (!isMountedRef.current || seq !== profileFetchSeqRef.current) return null;
  
        if (!profileData) {
          // Profile tidak ditemukan, coba buat
          const {
            data: { user: authUser },
          } = await supabase.auth.getUser();
  
          if (!isMountedRef.current || seq !== profileFetchSeqRef.current) return null;
  
          if (authUser) {
            const username =
              authUser.user_metadata?.username ||
              authUser.email?.split("@")[0] ||
              `user_${userId.substring(0, 8)}`;
  
            const { data: newProfile, error: createError } = await supabase
              .from("profiles")
              .insert({
                id: userId,
                username,
                full_name: authUser.user_metadata?.full_name || username,
                role: "user",
              })
              .select("id, username, role, full_name, avatar_url")
              .single();
  
            if (!createError && newProfile && isMountedRef.current) {
              setProfile(newProfile);
              return newProfile;
            }
          }
  
          if (isMountedRef.current) setProfile(null);
          return null;
        }
  
        if (isMountedRef.current) setProfile(profileData);
        return profileData;
      } catch (err) {
        console.error("[Auth] Error fetching profile:", err);
        if (isMountedRef.current) setProfile(null);
        return null;
      }
    }, []);
  
    const handleAuthEvent = useCallback(
      async (event, session) => {
        if (!isMountedRef.current) return;
  
        // Jika sedang processing, simpan event terakhir (supaya tidak hilang)
        if (isProcessingRef.current) {
          pendingAuthEventRef.current = { event, session };
          return;
        }
  
        isProcessingRef.current = true;
  
        try {
          // Pastikan init tidak “ketahan” loading gara-gara event handler
          setLoading(false);
  
          // Catatan: Supabase event umum: INITIAL_SESSION, SIGNED_IN, SIGNED_OUT, TOKEN_REFRESHED, USER_UPDATED
          if ((event === "SIGNED_IN" || event === "INITIAL_SESSION") && session?.user) {
            setUserSafe(session.user);
            await fetchProfile(session.user.id);
  
            // Migrasi favorit dari localStorage (non-blocking)
            migrateLocalStorageToSupabase(session.user.id).catch((e) => {
              console.warn("[Auth] Migration error:", e);
            });
          } else if (event === "SIGNED_OUT") {
            setUserSafe(null);
            setProfile(null);
          } else if (event === "TOKEN_REFRESHED" && session?.user) {
            // Refresh token kadang terjadi saat alt-tab / resume
            if (currentUserIdRef.current !== session.user.id) {
              setUserSafe(session.user);
            }
            // Profile tidak wajib selalu refetch, tapi aman untuk konsistensi
            await fetchProfile(session.user.id);
          } else if (event === "USER_UPDATED" && session?.user) {
            setUserSafe(session.user);
            // Optional: profile refresh jika metadata berubah
            await fetchProfile(session.user.id);
          }
        } catch (err) {
          console.error("[Auth] Error handling auth event:", err);
        } finally {
          isProcessingRef.current = false;
  
          // Jika ada event yang sempat tertahan, proses sekali lagi
          const pending = pendingAuthEventRef.current;
          pendingAuthEventRef.current = null;
          if (pending && isMountedRef.current) {
            // jangan await di finally chain panjang; tapi kita boleh await supaya urut
            await handleAuthEvent(pending.event, pending.session);
          }
        }
      },
      [fetchProfile, setUserSafe]
    );
  
    // INIT AUTH
    useEffect(() => {
      isMountedRef.current = true;
  
      if (!isSupabaseConfigured || !supabase) {
        console.log("[Auth] Supabase tidak dikonfigurasi");
        setLoading(false);
        setInitialized(true);
        return () => {
          isMountedRef.current = false;
        };
      }
  
      const attempt = ++initAttemptRef.current;
  
      const initAuth = async () => {
        try {
          const {
            data: { session },
            error,
          } = await supabase.auth.getSession();
  
          // Guard: kalau ada init baru, abaikan init lama
          if (!isMountedRef.current || attempt !== initAttemptRef.current) return;
  
          if (error) {
            console.warn("[Auth] Error getting session:", error.message);
          }
  
          if (session?.user) {
            setUserSafe(session.user);
            await fetchProfile(session.user.id);
          } else {
            setUserSafe(null);
            setProfile(null);
          }
        } catch (err) {
          console.error("[Auth] Error initializing:", err);
          if (isMountedRef.current && attempt === initAttemptRef.current) {
            setUserSafe(null);
            setProfile(null);
          }
        } finally {
          if (isMountedRef.current && attempt === initAttemptRef.current) {
            setLoading(false);
            setInitialized(true);
          }
        }
      };
  
      initAuth();
  
      const { data } = supabase.auth.onAuthStateChange(async (event, session) => {
        // Selalu tandai initialized supaya komponen lain tidak deadlock
        if (isMountedRef.current) setInitialized(true);
        await handleAuthEvent(event, session);
      });
  
      // (Opsional) re-sync saat tab aktif lagi (mengatasi kasus alt-tab)
      const onVisibility = async () => {
        if (!isMountedRef.current) return;
        if (document.visibilityState !== "visible") return;
  
        try {
          // getSession ringan dan sering memulihkan state yang “nyangkut”
          const {
            data: { session },
          } = await supabase.auth.getSession();
  
          if (!isMountedRef.current) return;
  
          if (session?.user) {
            setUserSafe(session.user);
            await fetchProfile(session.user.id);
          } else {
            setUserSafe(null);
            setProfile(null);
          }
        } catch (e) {
          console.warn("[Auth] visibility sync error:", e);
        } finally {
          if (isMountedRef.current) {
            setLoading(false);
            setInitialized(true);
          }
        }
      };
  
      document.addEventListener("visibilitychange", onVisibility);
  
      return () => {
        isMountedRef.current = false;
        try {
          data?.subscription?.unsubscribe?.();
        } catch {
          // ignore
        }
        document.removeEventListener("visibilitychange", onVisibility);
      };
    }, [fetchProfile, handleAuthEvent, setUserSafe]);
  
    // AUTH ACTIONS
    const signUp = useCallback(
      async (usernameOrEmail, password, extraMeta = {}) => {
        if (!supabase) return { error: { message: "Supabase tidak dikonfigurasi" } };
  
        const email = usernameToEmail(usernameOrEmail);
        if (!email) return { error: { message: "Username/email tidak valid" } };
  
        setLoading(true);
        try {
          const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
              data: {
                username: String(usernameOrEmail || "")
                  .toLowerCase()
                  .trim()
                  .replace(/\s+/g, ""),
                ...extraMeta,
              },
            },
          });
  
          return { data, error };
        } catch (err) {
          return { error: err };
        } finally {
          if (isMountedRef.current) setLoading(false);
        }
      },
      [usernameToEmail]
    );
  
    const signIn = useCallback(
      async (usernameOrEmail, password) => {
        if (!supabase) return { error: { message: "Supabase tidak dikonfigurasi" } };
  
        const email = usernameToEmail(usernameOrEmail);
        if (!email) return { error: { message: "Username/email tidak valid" } };
  
        setLoading(true);
        try {
          const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password,
          });
  
          return { data, error };
        } catch (err) {
          return { error: err };
        } finally {
          if (isMountedRef.current) setLoading(false);
        }
      },
      [usernameToEmail]
    );
  
    const signOut = useCallback(async () => {
      if (!supabase) return { error: { message: "Supabase tidak dikonfigurasi" } };
  
      setLoading(true);
      try {
        // Clear state dulu agar UI responsif
        currentUserIdRef.current = null;
        setUser(null);
        setProfile(null);
  
        const { error } = await supabase.auth.signOut();
  
        // Bersihkan cache terkait (opsional tapi membantu)
        try {
          const keysToRemove = [];
          for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (
              k &&
              (k.includes("supabase") ||
                k.includes("sb-") ||
                k.startsWith("cofind_favorites_") ||
                k.startsWith("cofind_want_to_visit_") ||
                k.startsWith("cache_"))
            ) {
              keysToRemove.push(k);
            }
          }
          keysToRemove.forEach((k) => {
            try {
              localStorage.removeItem(k);
            } catch {
              // ignore
            }
          });
        } catch {
          // ignore
        }
  
        return { error };
      } catch (err) {
        // Tetap clear state
        currentUserIdRef.current = null;
        setUser(null);
        setProfile(null);
        return { error: err };
      } finally {
        if (isMountedRef.current) setLoading(false);
      }
    }, []);
  
    const resetPassword = useCallback(
      async (usernameOrEmail) => {
        if (!supabase) return { error: { message: "Supabase tidak dikonfigurasi" } };
  
        const email = usernameToEmail(usernameOrEmail);
        if (!email) return { error: { message: "Username/email tidak valid" } };
  
        const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        });
  
        return { data, error };
      },
      [usernameToEmail]
    );
  
    const updatePassword = useCallback(async (newPassword) => {
      if (!supabase) return { error: { message: "Supabase tidak dikonfigurasi" } };
      const { data, error } = await supabase.auth.updateUser({ password: newPassword });
      return { data, error };
    }, []);
  
    const refreshProfile = useCallback(async () => {
      const uid = currentUserIdRef.current;
      if (uid) await fetchProfile(uid);
    }, [fetchProfile]);
  
    const value = useMemo(
      () => ({
        user,
        profile,
        loading,
        initialized,
        isAuthenticated: !!user,
        isAdmin: profile?.role === "admin",
        isSupabaseConfigured,
        signUp,
        signIn,
        signOut,
        resetPassword,
        updatePassword,
        refreshProfile,
      }),
      [
        user,
        profile,
        loading,
        initialized,
        signUp,
        signIn,
        signOut,
        resetPassword,
        updatePassword,
        refreshProfile,
      ]
    );
  
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
  }
  
  export { AuthContext, AuthProvider, useAuth};