/**
 * Error Tracking and Monitoring Utility
 * Tracks errors, timeouts, and auth issues for debugging
 */

const errorTracker = {
  errors: [],
  timeouts: [],
  authIssues: [],
  maxEntries: 100
};

/**
 * Track an error
 */
export const trackError = (error, context = {}) => {
  const entry = {
    id: Date.now() + Math.random(),
    timestamp: new Date().toISOString(),
    type: 'error',
    error: {
      message: error?.message || String(error),
      code: error?.code,
      name: error?.name,
      stack: error?.stack?.split('\n').slice(0, 5).join('\n')
    },
    context,
    url: window.location.href,
    userAgent: navigator.userAgent
  };

  errorTracker.errors.push(entry);
  if (errorTracker.errors.length > errorTracker.maxEntries) {
    errorTracker.errors.shift();
  }

  console.error('[Error Tracker]', entry);
  return entry;
};

/**
 * Track a timeout
 */
export const trackTimeout = (url, duration, context = {}) => {
  const entry = {
    id: Date.now() + Math.random(),
    timestamp: new Date().toISOString(),
    type: 'timeout',
    url,
    duration,
    context,
    url: window.location.href
  };

  errorTracker.timeouts.push(entry);
  if (errorTracker.timeouts.length > errorTracker.maxEntries) {
    errorTracker.timeouts.shift();
  }

  console.warn('[Error Tracker] Timeout:', entry);
  return entry;
};

/**
 * Track an auth issue
 */
export const trackAuthIssue = (issue, context = {}) => {
  const entry = {
    id: Date.now() + Math.random(),
    timestamp: new Date().toISOString(),
    type: 'auth',
    issue,
    context,
    url: window.location.href,
    state: {
      logoutFlag: localStorage.getItem('cofind_user_logged_out'),
      hasSession: !!localStorage.getItem('sb-auth-token')
    }
  };

  errorTracker.authIssues.push(entry);
  if (errorTracker.authIssues.length > errorTracker.maxEntries) {
    errorTracker.authIssues.shift();
  }

  console.warn('[Error Tracker] Auth Issue:', entry);
  return entry;
};

/**
 * Get all tracked errors
 */
export const getTrackedErrors = () => {
  return {
    errors: errorTracker.errors,
    timeouts: errorTracker.timeouts,
    authIssues: errorTracker.authIssues,
    summary: {
      totalErrors: errorTracker.errors.length,
      totalTimeouts: errorTracker.timeouts.length,
      totalAuthIssues: errorTracker.authIssues.length
    }
  };
};

/**
 * Clear all tracked errors
 */
export const clearTrackedErrors = () => {
  errorTracker.errors = [];
  errorTracker.timeouts = [];
  errorTracker.authIssues = [];
  console.log('✅ All tracked errors cleared');
};

/**
 * Get error summary
 */
export const getErrorSummary = () => {
  const summary = {
    errors: {
      total: errorTracker.errors.length,
      recent: errorTracker.errors.slice(-10),
      byType: errorTracker.errors.reduce((acc, e) => {
        acc[e.error?.name || 'Unknown'] = (acc[e.error?.name || 'Unknown'] || 0) + 1;
        return acc;
      }, {})
    },
    timeouts: {
      total: errorTracker.timeouts.length,
      recent: errorTracker.timeouts.slice(-10),
      averageDuration: errorTracker.timeouts.length > 0
        ? errorTracker.timeouts.reduce((sum, t) => sum + (t.duration || 0), 0) / errorTracker.timeouts.length
        : 0
    },
    authIssues: {
      total: errorTracker.authIssues.length,
      recent: errorTracker.authIssues.slice(-10),
      byIssue: errorTracker.authIssues.reduce((acc, a) => {
        acc[a.issue] = (acc[a.issue] || 0) + 1;
        return acc;
      }, {})
    }
  };

  console.group('📊 Error Summary');
  console.log('Errors:', summary.errors);
  console.log('Timeouts:', summary.timeouts);
  console.log('Auth Issues:', summary.authIssues);
  console.groupEnd();

  return summary;
};

// Expose to window
if (typeof window !== 'undefined') {
  window.__cofindErrorTracker = {
    trackError,
    trackTimeout,
    trackAuthIssue,
    getErrors: getTrackedErrors,
    getSummary: getErrorSummary,
    clear: clearTrackedErrors
  };
  
  console.log('🔧 Error Tracker Available: window.__cofindErrorTracker');
}

export default {
  trackError,
  trackTimeout,
  trackAuthIssue,
  getTrackedErrors,
  clearTrackedErrors,
  getErrorSummary
};
