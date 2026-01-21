/**
 * Frontend Auth Service - Interfaces with local SQLite backend
 * Replaces Supabase auth completely
 */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

class AuthService {
  constructor() {
    this.token = localStorage.getItem('auth_token');
    this.user = null;
  }

  // Helper: fetch with auth token
  async apiCall(endpoint, options = {}) {
    const headers = {
      'Accept': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    let body = options.body;
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
    if (body && typeof body !== 'string' && !isFormData) {
      body = JSON.stringify(body);
      headers['Content-Type'] = 'application/json';
    } else if (!isFormData && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      body,
    });

    const data = await response.json();

    if (!response.ok) {
      console.error(`[AuthService] API error: ${data.message}`);
      if (response.status === 401) {
        // Token expired or invalid
        this.logout();
      }
      throw new Error(data.message || 'API error');
    }

    return data;
  }

  // Sign Up
  async signup(email, username, password, fullName = '') {
    try {
      console.log('[AuthService] Signing up:', { email, username });
      
      const result = await this.apiCall('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({
          email,
          username,
          password,
          full_name: fullName,
        }),
      });

      if (result.status === 'success') {
        this.setToken(result.token);
        this.user = result.user;
        console.log('[AuthService] ✅ Signup successful:', this.user.username);
        return { success: true, user: this.user };
      }

      return { success: false, error: result.message };
    } catch (error) {
      console.error('[AuthService] Signup error:', error);
      return { success: false, error: error.message };
    }
  }

  // Login
  async login(email, password) {
    try {
      console.log('[AuthService] Logging in:', { email });
      
      const result = await this.apiCall('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });

      if (result.status === 'success') {
        this.setToken(result.token);
        this.user = result.user;
        console.log('[AuthService] ✅ Login successful:', this.user.username);
        return { success: true, user: this.user };
      }

      return { success: false, error: result.message };
    } catch (error) {
      console.error('[AuthService] Login error:', error);
      return { success: false, error: error.message };
    }
  }

  // Verify Session
  async verifySession() {
    try {
      if (!this.token) {
        console.log('[AuthService] No token found');
        return { valid: false, user: null };
      }

      console.log('[AuthService] Verifying token...');
      
      const result = await this.apiCall('/api/auth/verify', {
        method: 'POST',
        body: JSON.stringify({ token: this.token }),
      });

      if (result.status === 'success') {
        this.user = result.user;
        console.log('[AuthService] ✅ Token valid:', this.user.username);
        return { valid: true, user: this.user };
      }

      console.log('[AuthService] ❌ Token invalid');
      this.logout();
      return { valid: false, user: null };
    } catch (error) {
      console.error('[AuthService] Verification error:', error);
      this.logout();
      return { valid: false, user: null };
    }
  }

  // Get Current User
  async getCurrentUser() {
    try {
      if (!this.token) {
        return null;
      }

      const result = await this.apiCall('/api/auth/user', {
        method: 'GET',
      });

      if (result.status === 'success') {
        this.user = result.user;
        return this.user;
      }

      return null;
    } catch (error) {
      console.error('[AuthService] Get user error:', error);
      return null;
    }
  }

  // Update Profile
  async updateProfile(updates) {
    try {
      console.log('[AuthService] Updating profile...');
      
      const result = await this.apiCall('/api/auth/update-profile', {
        method: 'PUT',
        body: JSON.stringify(updates),
      });

      if (result.status === 'success') {
        this.user = result.user;
        console.log('[AuthService] ✅ Profile updated');
        return { success: true, user: this.user };
      }

      return { success: false, error: result.message };
    } catch (error) {
      console.error('[AuthService] Update profile error:', error);
      return { success: false, error: error.message };
    }
  }

  // Update Password
  async updatePassword(oldPassword, newPassword) {
    try {
      console.log('[AuthService] Updating password...');
      
      const result = await this.apiCall('/api/auth/update-password', {
        method: 'PUT',
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword,
        }),
      });

      if (result.status === 'success') {
        console.log('[AuthService] ✅ Password updated');
        return { success: true };
      }

      return { success: false, error: result.message };
    } catch (error) {
      console.error('[AuthService] Update password error:', error);
      return { success: false, error: error.message };
    }
  }

  // Logout
  async logout() {
    try {
      console.log('[AuthService] Logging out...');
      
      if (this.token) {
        await this.apiCall('/api/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ token: this.token }),
        });
      }

      this.clearToken();
      this.user = null;
      console.log('[AuthService] ✅ Logged out');
      return { success: true };
    } catch (error) {
      console.error('[AuthService] Logout error:', error);
      // Clear token anyway
      this.clearToken();
      return { success: false, error: error.message };
    }
  }

  // Token Management
  setToken(token) {
    this.token = token;
    localStorage.setItem('auth_token', token);
    console.log('[AuthService] Token saved to localStorage');
  }

  getToken() {
    return this.token || localStorage.getItem('auth_token');
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
    console.log('[AuthService] Token cleared');
  }

  isAuthenticated() {
    return !!this.token && !!this.user;
  }
}

// Export singleton instance
export const authService = new AuthService();
