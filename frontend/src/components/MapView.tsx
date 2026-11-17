import L from 'leaflet'
import { Fragment, memo, useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Marker, Pane, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { formatTime } from '../lib/format'
import { cumulativeMiles, pointAtMile, slice, type LatLng } from '../lib/geo'
import { RISK_COLOR } from '../lib/risk'
import { mileAt, ownedStretches } from '../lib/timeline'
import type { Checkpoint, HeatLayerKey, HeatmapResponse, PlanResponse, RouteOption } from '../types'
import HeatmapLayer from './HeatmapLayer'

interface Props {
  plan: PlanResponse | null
  heatmap: HeatmapResponse | null
  heatLayer: HeatLayerKey
  heatVisible: boolean
  hour: number
  selectedId: string | null
  onSelect: (id: string) => void
  focus: Checkpoint | null
}

const US_CENTER: LatLng = [39.5, -98.35]

function FitToPlan({ plan }: { plan: PlanResponse | null }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    const bounds = L.latLngBounds(plan.routes.flatMap((r) => r.geometry))
    map.flyToBounds(bounds, { padding: [40, 40], duration: 0.8 })
  }, [plan, map])
  return null
}

/** Keep Leaflet's size in sync with its container (responsive layout, sidebar changes). */
function AutoResize() {
  const map = useMap()
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])
  return null
}

function FocusCheckpoint({ cp }: { cp: Checkpoint | null }) {
  const map = useMap()
  useEffect(() => {
    if (cp) map.flyTo([cp.lat, cp.lon], Math.max(map.getZoom(), 9), { duration: 0.6 })
  }, [cp, map])
  return null
}

function CheckpointPopup({ cp, route }: { cp: Checkpoint; route: RouteOption }) {
  const w = cp.weather
  return (
    <div className="cp-popup">
      <div className="cp-popup__head">
        <strong>Route {route.id}</strong> · mile {Math.round(cp.mile)}
        <span className="pill" style={{ background: RISK_COLOR[cp.risk.level] }}>{cp.risk.label}</span>
      </div>
      <div>ETA {formatTime(cp.eta)}</div>
      <div>
        Wind {w.wind_mph.toFixed(0)} mph (gusts {w.gust_mph.toFixed(0)}) · Rain {w.rain_in_hr.toFixed(2)} in/hr · Snow{' '}
        {w.snow_in_hr.toFixed(2)} in/hr
      </div>
      {cp.risk.reasons.length > 0 && <div className="cp-popup__why">Why: {cp.risk.reasons.join('; ')}</div>}
    </div>
  )
}

/** Route lines and checkpoints. Memoised so dragging the forecast slider never re-renders them. */
const RouteLayers = memo(function RouteLayers({
  routes,
  selectedId,
  onSelect,
}: {
  routes: RouteOption[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const ordered = [...routes].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId))
  return (
    <>
      {ordered.map((r) => {
        const selected = r.id === selectedId
        const cum = cumulativeMiles(r.geometry, r.distance_mi)
        return (
          // Keyed on selection so the selected route re-mounts last and is drawn on top.
          <Fragment key={`${r.id}-${selected}`}>
            {selected ? (
              <>
                <Polyline positions={r.geometry} pathOptions={{ color: '#0f172a', weight: 10, opacity: 0.85 }} />
                {ownedStretches(r.checkpoints).map(({ from, to, cp }) =>
                  to > from ? (
                    <Polyline
                      key={cp.mile}
                      positions={slice(r.geometry, cum, from, to)}
                      pathOptions={{ color: RISK_COLOR[cp.risk.level], weight: 6, opacity: 1 }}
                    />
                  ) : null,
                )}
              </>
            ) : (
              <Polyline
                positions={r.geometry}
                pathOptions={{ color: r.recommended ? '#1d4ed8' : '#475569', weight: 5, opacity: 0.6 }}
                eventHandlers={{ click: () => onSelect(r.id) }}
              >
                <Tooltip sticky>Route {r.id} — click to inspect</Tooltip>
              </Polyline>
            )}
            {r.checkpoints.map((cp) => (
              <CircleMarker
                key={cp.mile}
                center={[cp.lat, cp.lon]}
                radius={selected ? 6 : 3.5}
                pathOptions={{
                  color: selected ? '#ffffff' : '#334155',
                  weight: selected ? 2 : 1,
                  fillColor: RISK_COLOR[cp.risk.level],
                  fillOpacity: selected ? 1 : 0.85,
                }}
                eventHandlers={{ click: () => onSelect(r.id) }}
              >
                <Popup>
                  <CheckpointPopup cp={cp} route={r} />
                </Popup>
              </CircleMarker>
            ))}
          </Fragment>
        )
      })}
    </>
  )
})

function truckIcon(id: string, selected: boolean) {
  return L.divIcon({
    className: '',
    html: `<div class="truck ${selected ? 'truck--selected' : ''}">${id}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  })
}

function TruckPositions({ routes, tMs, selectedId }: { routes: RouteOption[]; tMs: number; selectedId: string | null }) {
  const cums = useMemo(() => routes.map((r) => cumulativeMiles(r.geometry, r.distance_mi)), [routes])
  return (
    <>
      {routes.map((r, i) => {
        const mile = mileAt(r.checkpoints, tMs)
        if (mile === null) return null
        const pos = pointAtMile(r.geometry, cums[i], mile)
        return (
          <Marker key={r.id} position={pos} icon={truckIcon(r.id, r.id === selectedId)} zIndexOffset={r.id === selectedId ? 1000 : 0}>
            <Tooltip direction="top" offset={[0, -10]}>
              Route {r.id}: truck at mile {Math.round(mile)} at {formatTime(tMs)}
            </Tooltip>
          </Marker>
        )
      })}
    </>
  )
}

export default function MapView({ plan, heatmap, heatLayer, heatVisible, hour, selectedId, onSelect, focus }: Props) {
  const tMs = heatmap ? Date.parse(heatmap.start) + hour * 3600_000 : plan ? Date.parse(plan.departure) : 0
  return (
    <MapContainer center={US_CENTER} zoom={4} minZoom={3} maxZoom={16} className="map" preferCanvas zoomControl={false}>
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        attribution='Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors · Weather: <a href="https://open-meteo.com/">Open-Meteo</a> · Routing: <a href="https://project-osrm.org/">OSRM</a>'
        maxZoom={16}
      />
      {/* Place labels above the heatmap so cities stay readable. */}
      <Pane name="labels" style={{ zIndex: 380, pointerEvents: 'none' }}>
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}" maxZoom={16} />
      </Pane>
      {heatmap && <HeatmapLayer data={heatmap} layer={heatLayer} hour={hour} visible={heatVisible} />}
      {plan && (
        <>
          <RouteLayers routes={plan.routes} selectedId={selectedId} onSelect={onSelect} />
          <Pane name="endpoints" style={{ zIndex: 470 }}>
            {[
              { p: plan.origin, label: 'Origin' },
              { p: plan.destination, label: 'Destination' },
            ].map(({ p, label }) => (
              <CircleMarker key={label} center={[p.lat, p.lon]} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#0f172a', fillOpacity: 1 }}>
                <Tooltip permanent direction="top" offset={[0, -8]} className="endpoint-tip">
                  {label}: {p.name}
                </Tooltip>
              </CircleMarker>
            ))}
          </Pane>
          <TruckPositions routes={plan.routes} tMs={tMs} selectedId={selectedId} />
        </>
      )}
      <AutoResize />
      <FitToPlan plan={plan} />
      <FocusCheckpoint cp={focus} />
    </MapContainer>
  )
}
