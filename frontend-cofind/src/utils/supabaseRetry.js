/**
 * Enhanced Supabase Request with Retry Logic
 * Handles timeouts and retries automatically
 */

import { trackTimeout, trackError } from './errorTracker';

/**
 * Execute Supabase query with retry logic
 * @param {Function} queryFn - Function that returns Supabase query promise
 * @param {Object} options - Retry options
 * @returns {Promise} Query result
 */
export const executeWithRetry = async (queryFn, options = {}) => {
  const {
    maxRetries = 3,
    timeout = 30000,
    retryDelay = 1000,
    retryOnTimeout = true,
    retryOnNetworkError = true,
    onRetry = null
  } = options;

  let lastError = null;
  const startTime = Date.now();

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // Create timeout promise
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => {
          reject(new Error(`Request timeout after ${timeout / 1000} seconds`));
        }, timeout);
      });

      // Execute query with timeout
      const result = await Promise.race([queryFn(), timeoutPromise]);

      // Check if result has error
      if (result?.error) {
        const error = result.error;
        const isTimeout = error.message?.includes('timeout') || error.message?.includes('Timeout');
        const isNetworkError = error.message?.includes('network') || 
                              error.message?.includes('fetch') ||
                              error.message?.includes('Failed to fetch');

        // Decide if we should retry
        const shouldRetry = attempt < maxRetries && (
          (isTimeout && retryOnTimeout) ||
          (isNetworkError && retryOnNetworkError)
        );

        if (shouldRetry) {
          const delay = Math.min(retryDelay * Math.pow(2, attempt), 5000);
          console.warn(`[Supabase Retry] Attempt ${attempt + 1} failed, retrying in ${delay}ms...`, error.message);
          
          if (onRetry) {
            onRetry(attempt + 1, error, delay);
          }

          await new Promise(resolve => setTimeout(resolve, delay));
          lastError = error;
          continue;
        } else {
          // Don't retry - return error
          const duration = Date.now() - startTime;
          trackError(error, { attempt: attempt + 1, duration, action: 'supabaseQuery' });
          return result;
        }
      }

      // Success!
      const duration = Date.now() - startTime;
      if (attempt > 0) {
        console.log(`[Supabase Retry] ✅ Success after ${attempt + 1} attempts (${duration}ms)`);
      }
      return result;

    } catch (error) {
      const isTimeout = error.message?.includes('timeout') || error.message?.includes('Timeout');
      const isNetworkError = error.message?.includes('network') || 
                            error.message?.includes('fetch') ||
                            error.message?.includes('Failed to fetch');

      const shouldRetry = attempt < maxRetries && (
        (isTimeout && retryOnTimeout) ||
        (isNetworkError && retryOnNetworkError)
      );

      if (shouldRetry) {
        const delay = Math.min(retryDelay * Math.pow(2, attempt), 5000);
        console.warn(`[Supabase Retry] Attempt ${attempt + 1} timed out, retrying in ${delay}ms...`);
        
        if (onRetry) {
          onRetry(attempt + 1, error, delay);
        }

        await new Promise(resolve => setTimeout(resolve, delay));
        lastError = error;
        continue;
      } else {
        // Final attempt failed
        const duration = Date.now() - startTime;
        
        if (isTimeout) {
          trackTimeout(queryFn.toString(), timeout, { attempt: attempt + 1, duration });
        } else {
          trackError(error, { attempt: attempt + 1, duration, action: 'supabaseQuery' });
        }

        return { error, data: null };
      }
    }
  }

  // All retries exhausted
  const duration = Date.now() - startTime;
  trackError(lastError || new Error('All retries exhausted'), { 
    maxRetries, 
    duration, 
    action: 'supabaseQuery' 
  });

  return { error: lastError || new Error('All retries exhausted'), data: null };
};

/**
 * Wrapper for Supabase queries with automatic retry
 * @param {Function} queryFn - Function that returns Supabase query
 * @param {Object} options - Retry options
 * @returns {Promise} Query result
 */
export const withRetry = (queryFn, options = {}) => {
  return executeWithRetry(queryFn, options);
};

// Expose to window for debugging
if (typeof window !== 'undefined') {
  window.__cofindSupabaseRetry = {
    execute: executeWithRetry,
    withRetry
  };
  
  console.log('🔧 Supabase Retry Available: window.__cofindSupabaseRetry');
}

export default {
  executeWithRetry,
  withRetry
};
