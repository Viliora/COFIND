import React from 'react';
import { googleMapsDirectionsUrl } from '../utils/mapDirections';

/**
 * Tombol rute ringkas untuk popup peta (Leaflet/Google).
 * Membuka Google Maps di tab baru; origin opsional dari lokasi user.
 */
export default function MapDirectionsLink({
  userLocation = null,
  destination,
  className = '',
  label = 'Rute ➡',
}) {
  const href = googleMapsDirectionsUrl(userLocation, destination);
  if (!href) return null;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className={
        className ||
        'cofind-map-route-btn mt-2 inline-flex w-full items-center justify-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1.5 text-xs font-semibold !text-white no-underline transition-colors hover:bg-blue-700 hover:!text-white visited:!text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1'
      }
      style={{ color: '#ffffff' }}
    >
      <span className="text-white" style={{ color: '#ffffff' }}>
        {label}
      </span>
    </a>
  );
}
