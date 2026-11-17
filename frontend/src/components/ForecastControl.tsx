import { useEffect, useRef } from 'react'
import { formatTime, timeZoneLabel } from '../lib/format'
import { HEAT_SCALES, levelColor, RISK_COLOR, RISK_KEYS, RISK_LABEL } from '../lib/risk'
import type { HeatLayerKey, HeatmapResponse } from '../types'

interface Props {
  heatmap: HeatmapResponse | null
  loading: boolean
  error: string | null
  hour: number
  setHour: (h: number | ((h: number) => number)) => void
  playing: boolean
  setPlaying: (p: boolean) => void
  layer: HeatLayerKey
  setLayer: (l: HeatLayerKey) => void
  visible: boolean
  setVisible: (v: boolean) => void
}

const LAYERS: { key: HeatLayerKey; label: string }[] = [
  { key: 'risk', label: 'Risk' },
  { key: 'wind', label: 'Wind' },
  { key: 'rain', label: 'Rain' },
  { key: 'snow', label: 'Snow' },
]
const HOURS_PER_SECOND = 3

function Legend({ layer }: { layer: HeatLayerKey }) {
  if (layer === 'risk') {
    return (
      <div className="legend">
        {RISK_KEYS.map((k) => (
          <span key={k}>
            <i style={{ background: RISK_COLOR[k] }} />
            {RISK_LABEL[k]}
          </span>
        ))}
      </div>
    )
  }
  const s = HEAT_SCALES[layer]
  const gradient = `linear-gradient(90deg, ${[0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4].map((l) => levelColor(l).replace(/[\d.]+\)$/, '1)')).join(',')})`
  return (
    <div className="legend legend--scale">
      <div className="legend__bar" style={{ background: gradient }} />
      <div className="legend__ticks">
        {s.edges.map((e) => (
          <span key={e}>{e}</span>
        ))}
        <span className="unit">{s.unit}</span>
      </div>
    </div>
  )
}

export default function ForecastControl(p: Props) {
  const { heatmap, hour, setHour, playing, setPlaying } = p
  const max = heatmap ? heatmap.hours - 1 : 48
  const raf = useRef(0)

  // Smooth playback: advance by real elapsed time each animation frame (the layer interpolates between hours).
  useEffect(() => {
    if (!playing) return
    let last = performance.now()
    const tick = (now: number) => {
      const dt = (now - last) / 1000
      last = now
      setHour((h) => (h + dt * HOURS_PER_SECOND >= max ? 0 : h + dt * HOURS_PER_SECOND))
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [playing, max, setHour])

  const at = heatmap ? Date.parse(heatmap.start) + hour * 3600_000 : null

  return (
    <div className="forecast">
      <div className="forecast__row">
        <button className="icon-btn" onClick={() => setPlaying(!playing)} disabled={!heatmap} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          className="slider"
          min={0}
          max={max}
          step={0.05}
          value={hour}
          disabled={!heatmap}
          aria-label="Forecast hour"
          onChange={(e) => {
            setPlaying(false)
            setHour(Number(e.target.value))
          }}
        />
        <div className="forecast__time">
          {at ? (
            <>
              <strong>+{Math.floor(hour)} h</strong> {formatTime(at)} <small>{timeZoneLabel}</small>
            </>
          ) : p.loading ? (
            'Loading corridor forecast…'
          ) : (
            '0–48 h forecast'
          )}
        </div>
      </div>
      <div className="forecast__row forecast__row--opts">
        <div className="segmented segmented--sm" role="radiogroup" aria-label="Heatmap layer">
          {LAYERS.map((l) => (
            <button key={l.key} role="radio" aria-checked={p.layer === l.key} className={p.layer === l.key ? 'on' : ''} onClick={() => p.setLayer(l.key)}>
              {l.label}
            </button>
          ))}
        </div>
        <label className="check check--sm">
          <input type="checkbox" checked={p.visible} onChange={(e) => p.setVisible(e.target.checked)} /> Heatmap
        </label>
        <Legend layer={p.layer} />
      </div>
      {p.error && <div className="forecast__error">{p.error}</div>}
    </div>
  )
}
