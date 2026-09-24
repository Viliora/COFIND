import React, { useEffect, useRef } from 'react';
import { GOOGLE_MAPS_API_KEY } from '../config/mapsEnv';
import { formatDistanceKm, parseShopLatLng, distanceKmFromUser } from '../utils/geo';
import { googleMapsDirectionsUrl } from '../utils/mapDirections';

export default function RecommendationMapGoogle({ userLocation, shops = [] }) {
  const mapRef = useRef(null);

  useEffect(() => {
    const initMap = () => {
      if (!mapRef.current || !window.google) return;

      const defaultCenter = userLocation || { lat: -0.0263, lng: 109.3425 };
      const map = new window.google.maps.Map(mapRef.current, {
        center: defaultCenter,
        zoom: 14,
        disableDefaultUI: false,
        zoomControl: true,
        streetViewControl: false,
        mapTypeControl: false,
      });

      const bounds = new window.google.maps.LatLngBounds();

      if (userLocation) {
        new window.google.maps.Marker({
          position: userLocation,
          map,
          title: 'Lokasi Anda',
          icon: {
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 8,
            fillColor: '#2563EB',
            fillOpacity: 1,
            strokeWeight: 2,
            strokeColor: '#FFFFFF',
          },
        });
        bounds.extend(userLocation);
      }

      shops.forEach((shop, index) => {
        const coords = parseShopLatLng(shop);
        if (!coords) return;

        const rankIndex = typeof shop._mapRank === 'number' ? shop._mapRank : index;
        const distanceKm = distanceKmFromUser(userLocation, shop);
        const distanceLine =
          distanceKm != null
            ? `<p style="font-size: 11px; margin: 4px 0 0 0; color: #4f46e5; font-weight: 600;">± ${formatDistanceKm(distanceKm)} dari Anda</p>`
            : '';

        const marker = new window.google.maps.Marker({
          position: coords,
          map,
          label: {
            text: `${rankIndex + 1}`,
            color: '#FFFFFF',
            fontWeight: 'bold',
          },
          title: shop.name,
        });

        const directionsUrl = googleMapsDirectionsUrl(userLocation, coords);
        const routeBtn = directionsUrl
          ? `<a href="${directionsUrl}" target="_blank" rel="noopener noreferrer" style="display:flex;margin-top:8px;align-items:center;justify-content:center;border-radius:8px;background:#2563eb;color:#fff;font-size:12px;font-weight:600;padding:6px 10px;text-decoration:none;">Rute ➡</a>`
          : '';

        const infoWindow = new window.google.maps.InfoWindow({
          content: `
              <div style="color: #0f172a; padding: 4px; font-family: sans-serif; min-width:140px;">
                <b style="font-size: 13px;">${shop.name}</b>
                ${distanceLine}
                <p style="font-size: 11px; margin: 2px 0 0 0; color: #475569;">${shop.address || 'Pontianak'}</p>
                ${routeBtn}
              </div>
            `,
        });

        marker.addListener('click', () => {
          infoWindow.open(map, marker);
        });

        bounds.extend(coords);
      });

      if (shops.length > 0 || userLocation) {
        map.fitBounds(bounds, 50);
      }
    };

    if (!window.google) {
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}`;
      script.async = true;
      script.defer = true;
      script.onload = initMap;
      document.head.appendChild(script);
    } else {
      initMap();
    }
  }, [userLocation, shops]);

  return (
    <div className="w-full h-56 sm:h-64 rounded-2xl overflow-hidden border border-slate-200 dark:border-zinc-800 shadow-inner mt-4">
      <div ref={mapRef} className="w-full h-full" />
    </div>
  );
}
