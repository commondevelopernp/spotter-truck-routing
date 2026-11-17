import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, fetchHeatmap, planTrip } from './api'
import CheckpointTable from './components/CheckpointTable'
import ForecastControl from './components/ForecastControl'
import MapView from './components/MapView'
import RouteCards from './components/RouteCards'
import TripForm from './components/TripForm'
import { formatTime, timeZoneLabel } from './lib/format'
import type { Checkpoint, HeatLayerKey, HeatmapResponse, PlanRequest, PlanResponse } from './types'

const Results = memo(function Results({
  plan,
  selectedId,
  onSelect,
  onFocus,
}: {
  plan: PlanResponse
  selectedId: string | null
  onSelect: (id: string) => void
  onFocus: (cp: Checkpoint) => void
}) {
  const selected = plan.routes.find((r) => r.id === selectedId) ?? plan.routes[0]
  const rec = plan.recommendation
  return (
    <>
      <section className={`recommendation ${rec.all_no_travel ? 'recommendation--warn' : ''}`}>
        <div className="recommendation__title">
          {rec.all_no_travel ? '⚠ No safe route right now' : `Recommended: Route ${rec.route_id}`}
        </div>
        <p>{rec.reason}</p>
        <p className="muted">
          Departing {formatTime(plan.departure)} {timeZoneLabel} · {plan.load_lbs.toLocaleString()} lb · weather sampled every {plan.interval_mi} mi at the truck’s ETA
        </p>
      </section>
      <RouteCards plan={plan} selectedId={selectedId} onSelect={onSelect} />
      <section>
        <h2>Route {selected.id} checkpoints</h2>
        <CheckpointTable route={selected} onFocus={onFocus} />
      </section>
    </>
  )
})

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ field?: string; message: string } | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focus, setFocus] = useState<Checkpoint | null>(null)

  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null)
  const [heatLoading, setHeatLoading] = useState(false)
  const [heatError, setHeatError] = useState<string | null>(null)
  const [hour, setHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [heatLayer, setHeatLayer] = useState<HeatLayerKey>('risk')
  const [heatVisible, setHeatVisible] = useState(true)
  const abort = useRef<AbortController | null>(null)

  const submit = useCallback(async (req: PlanRequest) => {
    abort.current?.abort()
    const ctrl = new AbortController()
    abort.current = ctrl
    setLoading(true)
    setError(null)
    setPlaying(false)
    try {
      const p = await planTrip(req, ctrl.signal)
      setPlan(p)
      setSelectedId(p.recommendation.route_id)
      setHeatmap(null)
      setHour(0)
    } catch (e) {
      if (ctrl.signal.aborted) return
      setError(e instanceof ApiError ? { field: e.field, message: e.message } : { message: String(e) })
    } finally {
      if (!ctrl.signal.aborted) setLoading(false)
    }
  }, [])

  // The corridor heatmap loads after the routes so the main answer appears first.
  useEffect(() => {
    if (!plan) return
    const ctrl = new AbortController()
    setHeatLoading(true)
    setHeatError(null)
    fetchHeatmap(plan.plan_id, ctrl.signal)
      .then(setHeatmap)
      .catch((e) => !ctrl.signal.aborted && setHeatError(e instanceof Error ? e.message : String(e)))
      .finally(() => !ctrl.signal.aborted && setHeatLoading(false))
    return () => ctrl.abort()
  }, [plan])

  const onSelect = useCallback((id: string) => setSelectedId(id), [])
  const onFocus = useCallback((cp: Checkpoint) => setFocus(cp), [])

  return (
    <div className="layout">
      <aside className="sidebar">
        <header className="brand">
          <h1>Weather-Aware Truck Routing</h1>
          <p className="muted">Three route options, scored on weather along the way at the time you’ll actually be there.</p>
        </header>
        <TripForm loading={loading} onSubmit={submit} fieldError={error} />
        {error && !error.field && <div className="alert">{error.message}</div>}
        {loading && !plan && <div className="skeleton">Fetching routes and forecasts…</div>}
        {plan && <Results plan={plan} selectedId={selectedId} onSelect={onSelect} onFocus={onFocus} />}
      </aside>
      <main className="map-area">
        <MapView
          plan={plan}
          heatmap={heatmap}
          heatLayer={heatLayer}
          heatVisible={heatVisible}
          hour={hour}
          selectedId={selectedId}
          onSelect={onSelect}
          focus={focus}
        />
        {plan && (
          <ForecastControl
            heatmap={heatmap}
            loading={heatLoading}
            error={heatError}
            hour={hour}
            setHour={setHour}
            playing={playing}
            setPlaying={setPlaying}
            layer={heatLayer}
            setLayer={setHeatLayer}
            visible={heatVisible}
            setVisible={setHeatVisible}
          />
        )}
        {loading && <div className="map-loading">Planning…</div>}
      </main>
    </div>
  )
}
