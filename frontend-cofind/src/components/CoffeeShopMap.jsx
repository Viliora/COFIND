import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

const userLocationIcon = L.divIcon({
  className: 'user-location-marker',
  html: '<div style="width:24px;height:24px;background:#2563eb;border:3px solid white;border-radius:50%;box-shadow:0 2px 5px rgba(0,0,0,0.3);"></div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function formatRadius(m) {
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`;
  return `${m} m`;
}

function MapCenterToUser({ userLocation, radiusMeters }) {
  const map = useMap();
  const radiusKm = radiusMeters / 1000;
  useEffect(() => {
    if (!userLocation) return;
    map.setView([userLocation.lat, userLocation.lng], map.getZoom());
    const zoom = radiusKm <= 2 ? 14 : radiusKm <= 5 ? 13 : radiusKm <= 10 ? 12 : 11;
    map.setZoom(zoom);
  }, [userLocation, radiusMeters, radiusKm, map]);
  return null;
}

function MapBounds({ shops, userLocation }) {
  const map = useMap();

  useEffect(() => {
    const points = shops
      .filter((shop) => shop.latitude != null && shop.longitude != null)
      .map((shop) => [shop.latitude, shop.longitude]);
    if (userLocation) {
      points.push([userLocation.lat, userLocation.lng]);
    }
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 14);
      return;
    }
    map.fitBounds(L.latLngBounds(points), { padding: [50, 50], maxZoom: 15 });
  }, [shops, userLocation, map]);

  return null;
}

export default function CoffeeShopMap({
  coffeeShops = [],
  userLocation = null,
  radiusMeters = 2000,
  setRadiusMeters,
  locationLoading = false,
  locationError = null,
  getCurrentLocation,
  shopsInRadius = [],
}) {
  const allWithCoords = useMemo(
    () => coffeeShops.filter((shop) => shop.latitude != null && shop.longitude != null),
    [coffeeShops],
  );

  const markers = userLocation ? shopsInRadius : allWithCoords;

  const centerLat = userLocation?.lat
    ?? (allWithCoords.length > 0
      ? allWithCoords.reduce((sum, shop) => sum + shop.latitude, 0) / allWithCoords.length
      : -0.0311);

  const centerLng = userLocation?.lng
    ?? (allWithCoords.length > 0
      ? allWithCoords.reduce((sum, shop) => sum + shop.longitude, 0) / allWithCoords.length
      : 109.337);

  if (allWithCoords.length === 0) {
    return (
      <div className="mb-6 sm:mb-8 w-full rounded-lg border border-gray-200 bg-gray-100 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex h-64 items-center justify-center p-4">
          <p className="text-center text-gray-500 dark:text-gray-400">
            Tidak ada data koordinat untuk ditampilkan di peta
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 sm:mb-8 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="border-b border-gray-200 p-4 sm:p-5 dark:border-gray-700">
        <h2 className="mb-2 flex items-center gap-2 text-xl font-bold text-gray-800 dark:text-gray-200 sm:text-2xl">
          <span className="text-2xl" aria-hidden>
            🗺️
          </span>
          Peta coffee shop
        </h2>
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          {userLocation
            ? `Menampilkan toko dalam radius ${formatRadius(radiusMeters)} dari lokasi Anda.`
            : 'Semua coffee shop di peta. Aktifkan lokasi untuk filter radius.'}
        </p>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={getCurrentLocation}
            disabled={locationLoading || !getCurrentLocation}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {locationLoading ? (
              <>
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Mengambil lokasi...
              </>
            ) : (
              <>
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                Dapatkan lokasi saya
              </>
            )}
          </button>
          {userLocation && typeof setRadiusMeters === 'function' ? (
            <div className="flex items-center gap-3">
              <label className="whitespace-nowrap text-sm font-medium text-gray-700 dark:text-gray-300">
                Radius:{' '}
                <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                  {formatRadius(radiusMeters)}
                </span>
              </label>
              <input
                type="range"
                min={0}
                max={5000}
                step={10}
                value={radiusMeters}
                onChange={(e) => setRadiusMeters(Number(e.target.value))}
                className="h-2 w-32 cursor-pointer appearance-none rounded-lg bg-gray-200 accent-indigo-600 sm:w-40 dark:bg-gray-600"
                aria-label="Radius pencarian"
              />
            </div>
          ) : null}
        </div>
        {locationError ? (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">{locationError}</p>
        ) : null}
      </div>

      <div className="h-80 w-full sm:h-96">
        <MapContainer
          center={[centerLat, centerLng]}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom
          className="z-0"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {userLocation ? (
            <>
              <MapCenterToUser userLocation={userLocation} radiusMeters={radiusMeters} />
              <Circle
                center={[userLocation.lat, userLocation.lng]}
                radius={radiusMeters}
                pathOptions={{
                  color: '#4f46e5',
                  fillColor: '#6366f1',
                  fillOpacity: 0.15,
                  weight: 2,
                }}
              />
              <Marker position={[userLocation.lat, userLocation.lng]} icon={userLocationIcon}>
                <Popup>Lokasi Anda</Popup>
              </Marker>
            </>
          ) : (
            <MapBounds shops={allWithCoords} userLocation={null} />
          )}
          {userLocation ? <MapBounds shops={markers} userLocation={userLocation} /> : null}
          {markers.map((shop) => (
            <Marker key={shop.place_id || shop.id} position={[shop.latitude, shop.longitude]}>
              <Popup>
                <div className="p-2">
                  <h3 className="mb-1 text-sm font-semibold text-gray-800">{shop.name}</h3>
                  {shop._distanceKm != null ? (
                    <p className="mb-1 text-xs font-medium text-indigo-600">
                      {shop._distanceKm.toFixed(1)} km
                    </p>
                  ) : null}
                  {shop.address ? (
                    <p className="mb-1 text-xs text-gray-600">📍 {shop.address}</p>
                  ) : null}
                  {shop.rating ? (
                    <p className="text-xs text-gray-600">
                      ⭐ {Number(shop.rating).toFixed(1)}
                      {shop.total_reviews ? (
                        <span className="ml-1">({shop.total_reviews} reviews)</span>
                      ) : null}
                    </p>
                  ) : null}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      {userLocation && markers.length === 0 ? (
        <p className="border-t border-gray-200 px-4 py-3 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-400">
          Tidak ada coffee shop dalam radius {formatRadius(radiusMeters)}. Coba perbesar radius.
        </p>
      ) : null}
    </div>
  );
}
