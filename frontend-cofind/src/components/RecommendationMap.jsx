import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import { formatDistanceKm, parseShopLatLng, distanceKmFromUser } from '../utils/geo';
import { useGoogleRecommendationMap } from '../config/mapsEnv';
import RecommendationMapGoogle from './RecommendationMapGoogle';
import MapDirectionsLink from './MapDirectionsLink';

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

function createNumberedShopIcon(index) {
  const n = index + 1;
  return L.divIcon({
    className: 'recommendation-number-marker',
    html: `<div style="width:28px;height:28px;background:#dc2626;border:2px solid #fff;border-radius:50%;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.35);">${n}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function FitRecommendationBounds({ userLocation, shopsWithCoords }) {
  const map = useMap();
  useEffect(() => {
    const points = shopsWithCoords.map((s) => [s.coords.lat, s.coords.lng]);
    if (userLocation) points.push([userLocation.lat, userLocation.lng]);
    if (!points.length) return;
    if (points.length === 1) {
      map.setView(points[0], 14);
      return;
    }
    map.fitBounds(L.latLngBounds(points), { padding: [48, 48], maxZoom: 15 });
  }, [userLocation, shopsWithCoords, map]);
  return null;
}

function RecommendationMapLeaflet({ userLocation, shops = [] }) {
  const shopsWithCoords = useMemo(
    () =>
      shops
        .map((shop, index) => {
          const coords = parseShopLatLng(shop);
          if (!coords) return null;
          const distanceKm = distanceKmFromUser(userLocation, shop);
          const rankIndex =
            typeof shop._mapRank === 'number' ? shop._mapRank : index;
          return { shop, index: rankIndex, coords, distanceKm };
        })
        .filter(Boolean),
    [shops, userLocation],
  );

  const defaultCenter = userLocation || { lat: -0.0263, lng: 109.3425 };

  return (
    <div className="w-full h-56 sm:h-64 rounded-2xl overflow-hidden border border-slate-200 dark:border-zinc-800 shadow-inner mt-4">
      <MapContainer
        center={[defaultCenter.lat, defaultCenter.lng]}
        zoom={14}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom
        className="z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitRecommendationBounds userLocation={userLocation} shopsWithCoords={shopsWithCoords} />
        {userLocation ? (
          <Marker position={[userLocation.lat, userLocation.lng]} icon={userLocationIcon}>
            <Popup>Lokasi Anda</Popup>
          </Marker>
        ) : null}
        {shopsWithCoords.map(({ shop, index, coords, distanceKm }) => (
          <Marker
            key={shop.place_id || `${shop.name}-${index}`}
            position={[coords.lat, coords.lng]}
            icon={createNumberedShopIcon(index)}
          >
            <Popup>
              <div className="min-w-[140px] p-0.5 text-slate-900">
                <p className="text-sm font-semibold">{shop.name}</p>
                {distanceKm != null ? (
                  <p className="text-xs font-medium text-indigo-600 mt-0.5">
                    ± {formatDistanceKm(distanceKm)} dari Anda
                  </p>
                ) : null}
                {shop.address ? (
                  <p className="text-[11px] text-slate-600 mt-1">{shop.address}</p>
                ) : null}
                <MapDirectionsLink userLocation={userLocation} destination={coords} />
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

/**
 * Peta rekomendasi: default Leaflet (dev & production tanpa kuota Google).
 * Set VITE_MAP_PROVIDER=google + VITE_GOOGLE_MAPS_API_KEY di frontend-cofind/.env (lokal)
 * atau Vercel Environment Variables (production). Jangan commit .env.
 * Jarak ke marker ditampilkan jika userLocation tersedia (Haversine).
 */
export default function RecommendationMap(props) {
  if (useGoogleRecommendationMap) {
    return <RecommendationMapGoogle {...props} />;
  }
  return <RecommendationMapLeaflet {...props} />;
}
