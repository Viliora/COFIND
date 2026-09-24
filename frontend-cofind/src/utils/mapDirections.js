/** URL Google Maps Directions (setara tombol “Rute”, tanpa Maps JavaScript API). */
export function googleMapsDirectionsUrl(userLocation, destination) {
  const lat = destination?.lat;
  const lng = destination?.lng;
  if (lat == null || lng == null || Number.isNaN(Number(lat)) || Number.isNaN(Number(lng))) {
    return null;
  }
  const params = new URLSearchParams({
    api: '1',
    destination: `${lat},${lng}`,
    travelmode: 'driving',
  });
  if (userLocation?.lat != null && userLocation?.lng != null) {
    params.set('origin', `${userLocation.lat},${userLocation.lng}`);
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
