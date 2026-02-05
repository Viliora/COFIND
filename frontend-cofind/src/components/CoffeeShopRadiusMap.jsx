import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import CoffeeShopCard from './CoffeeShopCard';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Icon untuk lokasi user (pin biru/hijau)
const userLocationIcon = L.divIcon({
  className: 'user-location-marker',
  html: '<div style="width:24px;height:24px;background:#2563eb;border:3px solid white;border-radius:50%;box-shadow:0 2px 5px rgba(0,0,0,0.3);"></div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12]
});

// Format radius untuk tampilan (meter atau km)
function formatRadius(m) {
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`;
  return `${m} m`;
}

// Update peta: center + zoom agar circle radius terlihat
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

export default function CoffeeShopRadiusMap({
  userLocation,
  radiusMeters,
  setRadiusMeters,
  locationLoading,
  locationError,
  getCurrentLocation,
  shopsInRadius = []
}) {
  const centerLat = userLocation?.lat ?? -0.0311;
  const centerLng = userLocation?.lng ?? 109.337;

  return (
    <div className="mb-8 sm:mb-10 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-gray-800 shadow-lg">
      {/* Header & kontrol dalam div yang sama */}
      <div className="p-4 sm:p-5 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2 mb-2">
          <span className="text-2xl">📍</span>
          Coffee shop dalam radius
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Aktifkan lokasi lalu geser radius untuk melihat coffee shop di sekitar Anda. Peta dan katalog hanya menampilkan coffee shop dalam radius.
        </p>
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <button
            type="button"
            onClick={getCurrentLocation}
            disabled={locationLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {locationLoading ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Mengambil lokasi...
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Dapatkan lokasi saya
              </>
            )}
          </button>
          {userLocation && (
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                Radius: <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{formatRadius(radiusMeters)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={5000}
                step={10}
                value={radiusMeters}
                onChange={(e) => setRadiusMeters(Number(e.target.value))}
                className="w-32 sm:w-40 h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
            </div>
          )}
        </div>
        {locationError && (
          <p className="text-sm text-red-600 dark:text-red-400 mt-3">{locationError}</p>
        )}
      </div>

      {/* Peta Leaflet + Katalog dalam satu blok (peta di atas, katalog di bawah) */}
      {userLocation && (
        <>
          <div className="w-full h-80 sm:h-96 border-b border-gray-200 dark:border-gray-700">
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
              <MapCenterToUser userLocation={userLocation} radiusMeters={radiusMeters} />
              <Circle
                center={[userLocation.lat, userLocation.lng]}
                radius={radiusMeters}
                pathOptions={{
                  color: '#4f46e5',
                  fillColor: '#6366f1',
                  fillOpacity: 0.15,
                  weight: 2
                }}
              />
              <Marker position={[userLocation.lat, userLocation.lng]} icon={userLocationIcon}>
                <Popup>Lokasi Anda</Popup>
              </Marker>
              {shopsInRadius.map((shop) => (
                <Marker
                  key={shop.place_id}
                  position={[shop.latitude, shop.longitude]}
                >
                  <Popup>
                    <div className="p-2">
                      <h3 className="font-semibold text-sm mb-1 text-gray-800">{shop.name}</h3>
                      {shop._distanceKm != null && (
                        <p className="text-xs text-indigo-600 font-medium mb-1">
                          {shop._distanceKm.toFixed(1)} km
                        </p>
                      )}
                      {shop.address && (
                        <p className="text-xs text-gray-600 mb-1">📍 {shop.address}</p>
                      )}
                      {shop.rating && (
                        <p className="text-xs text-gray-600">⭐ {shop.rating.toFixed(1)}</p>
                      )}
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>

          {/* Katalog coffee shop dalam radius (di dalam div yang sama) */}
          <div className="p-4 sm:p-5">
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {shopsInRadius.length} coffee shop dalam radius {formatRadius(radiusMeters)} dari lokasi Anda
            </p>
            {shopsInRadius.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
                {shopsInRadius.map((shop) => (
                  <div key={shop.place_id} className="relative">
                    <div className="absolute top-2 right-2 z-10 px-2 py-1 rounded bg-indigo-600 text-white text-xs font-medium">
                      {shop._distanceKm.toFixed(1)} km
                    </div>
                    <CoffeeShopCard shop={shop} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700">
                <p className="text-gray-600 dark:text-gray-400">
                  Tidak ada coffee shop dalam radius {formatRadius(radiusMeters)}. Coba perbesar radius.
                </p>
              </div>
            )}
          </div>
        </>
      )}

      {!userLocation && (
        <div className="p-8 text-center bg-gray-50 dark:bg-gray-800/50">
          <p className="text-gray-600 dark:text-gray-400">
            Klik &quot;Dapatkan lokasi saya&quot; untuk menampilkan peta dan katalog coffee shop dalam radius.
          </p>
        </div>
      )}
    </div>
  );
}
