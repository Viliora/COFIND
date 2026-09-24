/** Konfigurasi peta rekomendasi — baca env Vite di satu tempat (jangan hardcode key). */

export const MAP_PROVIDER = (import.meta.env.VITE_MAP_PROVIDER || 'leaflet').toLowerCase();

export const GOOGLE_MAPS_API_KEY = String(import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim();

export const useGoogleRecommendationMap =
  MAP_PROVIDER === 'google' && GOOGLE_MAPS_API_KEY.length > 0;
