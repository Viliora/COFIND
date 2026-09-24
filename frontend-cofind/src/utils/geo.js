/** Jarak garis lurus (Haversine) dalam kilometer — cukup akurat untuk label jarak UI. */
export function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/** Tampilan jarak: &lt; 1 km dalam meter, selain itu km dengan 1 desimal. */
export function formatDistanceKm(distanceKm) {
  if (distanceKm == null || Number.isNaN(distanceKm)) return null;
  if (distanceKm < 1) return `${Math.round(distanceKm * 1000)} m`;
  return `${distanceKm.toFixed(1)} km`;
}

export function parseShopLatLng(shop) {
  if (!shop) return null;
  const lat = parseFloat(shop.latitude ?? shop.lat);
  const lng = parseFloat(shop.longitude ?? shop.lng);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
  return { lat, lng };
}

export function distanceKmFromUser(userLocation, shop) {
  const coords = parseShopLatLng(shop);
  if (userLocation?.lat == null || userLocation?.lng == null || !coords) return null;
  return haversineKm(userLocation.lat, userLocation.lng, coords.lat, coords.lng);
}
