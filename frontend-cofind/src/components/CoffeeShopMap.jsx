import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix untuk default marker icon di Leaflet dengan Vite
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// Komponen untuk auto-fit bounds
function MapBounds({ shops }) {
  const map = useMap();
  
  useEffect(() => {
    if (shops.length > 0) {
      const bounds = shops
        .filter(shop => shop.latitude && shop.longitude)
        .map(shop => [shop.latitude, shop.longitude]);
      
      if (bounds.length > 0) {
        map.fitBounds(bounds, {
          padding: [50, 50],
          maxZoom: 15
        });
      }
    }
  }, [shops, map]);
  
  return null;
}

export default function CoffeeShopMap({ coffeeShops = [] }) {
  const mapRef = useRef(null);
  
  // Filter coffee shops yang punya lat/long
  const shopsWithCoords = coffeeShops.filter(
    shop => shop.latitude != null && shop.longitude != null
  );
  
  // Hitung center point (rata-rata dari semua koordinat)
  const centerLat = shopsWithCoords.length > 0
    ? shopsWithCoords.reduce((sum, shop) => sum + shop.latitude, 0) / shopsWithCoords.length
    : -0.0311; // Default: Pontianak
  
  const centerLng = shopsWithCoords.length > 0
    ? shopsWithCoords.reduce((sum, shop) => sum + shop.longitude, 0) / shopsWithCoords.length
    : 109.3370; // Default: Pontianak
  
  if (shopsWithCoords.length === 0) {
    return (
      <div className="w-full h-64 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center">
        <p className="text-gray-500 dark:text-gray-400">
          Tidak ada data koordinat untuk ditampilkan di map
        </p>
      </div>
    );
  }
  
  return (
    <div className="w-full mb-6 sm:mb-8">
      <div className="w-full h-80 sm:h-96 rounded-lg overflow-hidden shadow-lg border border-gray-200 dark:border-gray-700">
        <MapContainer
          center={[centerLat, centerLng]}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={true}
          className="z-0"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          <MapBounds shops={shopsWithCoords} />
          
          {shopsWithCoords.map((shop) => (
            <Marker
              key={shop.id || shop.place_id}
              position={[shop.latitude, shop.longitude]}
            >
              <Popup>
                <div className="p-2">
                  <h3 className="font-semibold text-sm mb-1 text-gray-800">
                    {shop.name}
                  </h3>
                  {shop.address && (
                    <p className="text-xs text-gray-600 mb-1">
                      📍 {shop.address}
                    </p>
                  )}
                  {shop.rating && (
                    <p className="text-xs text-gray-600">
                      ⭐ {shop.rating.toFixed(1)}
                      {shop.total_reviews && (
                        <span className="ml-1">({shop.total_reviews} reviews)</span>
                      )}
                    </p>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
