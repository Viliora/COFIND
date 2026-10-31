/**
 * Simpan sesi rekomendasi AI terakhir per user (sessionStorage).
 * Bertahan saat refresh halaman; hilang saat tab/jendela ditutup.
 */

const STORAGE_KEY = 'cofind_last_recommendation_session';

function getStorage() {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null;
  } catch {
    return null;
  }
}

/** Hapus salinan lama di localStorage (perilaku sebelumnya). */
function clearLegacyLocalStorage() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

function normalizeUserId(userId) {
  if (userId == null || userId === '') return null;
  return String(userId);
}

/**
 * @param {object} payload
 * @param {string|number} payload.userId
 * @param {Array} payload.recommendations
 * @param {Array} [payload.otherOptions]
 * @param {string[]} [payload.confirmedPills]
 * @param {string[]} [payload.confirmedAttributes]
 * @param {string} [payload.confirmedSearchKeyword]
 * @param {number|null} [payload.totalDurationSeconds]
 */
export function saveLastRecommendationSession(payload) {
  const userId = normalizeUserId(payload?.userId);
  const recommendations = Array.isArray(payload?.recommendations)
    ? payload.recommendations
    : [];
  if (!userId || recommendations.length === 0) return;

  try {
    const session = {
      userId,
      recommendations,
      otherOptions: Array.isArray(payload.otherOptions) ? payload.otherOptions : [],
      confirmedPills: Array.isArray(payload.confirmedPills) ? payload.confirmedPills : [],
      confirmedAttributes: Array.isArray(payload.confirmedAttributes)
        ? payload.confirmedAttributes
        : [],
      confirmedSearchKeyword: String(payload.confirmedSearchKeyword || '').trim(),
      totalDurationSeconds:
        payload.totalDurationSeconds != null
          ? Number(payload.totalDurationSeconds)
          : null,
      savedAt: new Date().toISOString(),
    };
    clearLegacyLocalStorage();
    const storage = getStorage();
    if (!storage) return;
    storage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch (error) {
    console.warn('[LastRecommendationSession] Gagal menyimpan:', error);
  }
}

/**
 * @param {string|number|null|undefined} userId
 * @returns {object|null}
 */
export function loadLastRecommendationSession(userId) {
  const uid = normalizeUserId(userId);
  if (!uid) return null;
  try {
    clearLegacyLocalStorage();
    const storage = getStorage();
    if (!storage) return null;
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || normalizeUserId(parsed.userId) !== uid) return null;
    if (!Array.isArray(parsed.recommendations) || parsed.recommendations.length === 0) {
      return null;
    }
    return parsed;
  } catch (error) {
    console.warn('[LastRecommendationSession] Gagal membaca:', error);
    return null;
  }
}

export function clearLastRecommendationSession() {
  try {
    clearLegacyLocalStorage();
    const storage = getStorage();
    if (storage) storage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.warn('[LastRecommendationSession] Gagal menghapus:', error);
  }
}

/**
 * Terapkan payload sesi ke setter React (ShopList).
 * @param {object|null} session
 * @param {object} setters
 */
export function applyLastRecommendationSession(session, setters) {
  if (!session?.recommendations?.length) return false;
  setters.setLlmRecommendations(session.recommendations);
  if (setters.setLlmOtherOptions) {
    setters.setLlmOtherOptions(
      Array.isArray(session.otherOptions) ? session.otherOptions : [],
    );
  }
  setters.setConfirmedPills(session.confirmedPills || []);
  setters.setConfirmedAttributes(session.confirmedAttributes || []);
  setters.setConfirmedSearchKeyword(session.confirmedSearchKeyword || '');
  const total = session.totalDurationSeconds;
  setters.setRecommendationTotalSeconds(
    total != null && Number.isFinite(Number(total)) ? Number(total) : null,
  );
  return true;
}
