import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

interface IpMapProps {
  lat: number
  lon: number
  label?: string
  className?: string
}

function isInChina(lat: number, lon: number): boolean {
  return lat >= 3 && lat <= 54 && lon >= 73 && lon <= 136
}

export default function IpMap({ lat, lon, label, className = '' }: IpMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)

  useEffect(() => {
    if (!mapRef.current) return

    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove()
      mapInstanceRef.current = null
    }

    const map = L.map(mapRef.current, {
      center: [lat, lon],
      zoom: 13,
      scrollWheelZoom: true,
    })

    if (isInChina(lat, lon)) {
      L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
        attribution: '&copy; 高德地图',
        maxZoom: 18,
        subdomains: '1234',
      }).addTo(map)
    } else {
      L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map)
    }

    const icon = L.icon({
      iconUrl: markerIcon,
      iconRetinaUrl: markerIcon2x,
      shadowUrl: markerShadow,
      iconSize: [25, 41],
      iconAnchor: [12, 41],
    })

    L.marker([lat, lon], { icon })
      .addTo(map)
      .bindPopup(label || `${lat.toFixed(4)}, ${lon.toFixed(4)}`)
      .openPopup()

    mapInstanceRef.current = map
    return () => {
      map.remove()
      mapInstanceRef.current = null
    }
  }, [lat, lon, label])

  return (
    <div
      ref={mapRef}
      className={`relative z-0 rounded-lg overflow-hidden border border-theme-border ${className}`}
      style={{ height: 280, minHeight: 280 }}
    />
  )
}
