import { authService } from './authService';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

function buildQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, value);
    }
  });
  const queryString = query.toString();
  return queryString ? `?${queryString}` : '';
}

async function apiCall(endpoint, options = {}) {
  const token = authService.getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = { status: 'error', message: 'Invalid JSON response from server' };
  }

  if (!response.ok) {
    throw new Error(data?.message || 'Request failed');
  }

  return data;
}

export const adminService = {
  getDashboard() {
    return apiCall('/api/admin/dashboard');
  },

  getUsers(params = {}) {
    return apiCall(`/api/admin/users${buildQuery(params)}`);
  },

  createUser(payload) {
    return apiCall('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  updateUser(userId, payload) {
    return apiCall(`/api/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  deleteUser(userId) {
    return apiCall(`/api/admin/users/${userId}`, {
      method: 'DELETE',
    });
  },

  getShops(params = {}) {
    return apiCall(`/api/admin/shops${buildQuery(params)}`);
  },

  getFacilityEntry(placeId) {
    return apiCall(`/api/admin/facilities/${placeId}`);
  },

  updateFacilityEntry(placeId, payload) {
    return apiCall(`/api/admin/facilities/${placeId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  createShop(payload) {
    return apiCall('/api/admin/shops', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  updateShop(placeId, payload) {
    return apiCall(`/api/admin/shops/${placeId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  deleteShop(placeId) {
    return apiCall(`/api/admin/shops/${placeId}`, {
      method: 'DELETE',
    });
  },

  getReviews(params = {}) {
    return apiCall(`/api/admin/reviews${buildQuery(params)}`);
  },

  getReviewReports(params = {}) {
    return apiCall(`/api/admin/review-reports${buildQuery(params)}`);
  },

  updateReviewReport(reportId, payload) {
    return apiCall(`/api/admin/review-reports/${reportId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  deleteReview(reviewId) {
    return apiCall(`/api/admin/reviews/${reviewId}`, {
      method: 'DELETE',
    });
  },

  getPreferenceSuggestions(params = {}) {
    return apiCall(`/api/admin/preference-suggestions${buildQuery(params)}`);
  },

  deletePreferenceSuggestion(suggestionId) {
    return apiCall(`/api/admin/preference-suggestions/${suggestionId}`, {
      method: 'DELETE',
    });
  },

  getAICache() {
    return apiCall('/api/admin/ai/cache');
  },

  deleteAICache(placeId) {
    return apiCall(`/api/admin/ai/cache/${placeId}`, {
      method: 'DELETE',
    });
  },

  triggerSentimentAnalysis(payload) {
    return apiCall('/api/llm/analyze-sentiment', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getSettings() {
    return apiCall('/api/admin/settings');
  },
};
