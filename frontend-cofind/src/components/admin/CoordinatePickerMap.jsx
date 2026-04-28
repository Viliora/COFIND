import React, { useMemo } from 'react';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const defaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

L.Marker.prototype.options.icon = defaultIcon;

function PickerMarker({ value, onChange }) {
  useMapEvents({
    click(event) {
      onChange({
        lat: Number(event.latlng.lat.toFixed(6)),
        lng: Number(event.latlng.lng.toFixed(6)),
      });
    },
  });

  if (!value?.lat || !value?.lng) return null;
  return <Marker position={[value.lat, value.lng]} />;
}

export default function CoordinatePickerMap({ latitude, longitude, onChange }) {
  const center = useMemo(() => {
    if (latitude && longitude) return [latitude, longitude];
    return [-0.02633, 109.3425];
  }, [latitude, longitude]);

  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-zinc-700">
      <MapContainer center={center} zoom={13} scrollWheelZoom className="h-72 w-full z-0">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <PickerMarker
          value={{ lat: latitude, lng: longitude }}
          onChange={({ lat, lng }) => onChange(lat, lng)}
        />
      </MapContainer>
    </div>
  );
}
