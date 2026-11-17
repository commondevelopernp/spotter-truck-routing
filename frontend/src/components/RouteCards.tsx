import { formatDuration, formatMiles, formatTime } from '../lib/format'
import { RISK_COLOR, RISK_KEYS, RISK_LABEL } from '../lib/risk'
import type { PlanResponse } from '../types'

interface Props {
  plan: PlanResponse
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function RouteCards({ plan, selectedId, onSelect }: Props) {
  const routes = [...plan.routes].sort((a, b) => a.rank - b.rank)
  return (
    <div className="cards">
      {routes.map((r) => {
        const s = r.summary
        const total = s.distance_mi || 1
        return (
          <button key={r.id} className={`card ${r.id === selectedId ? 'card--selected' : ''}`} onClick={() => onSelect(r.id)} aria-pressed={r.id === selectedId}>
            <div className="card__head">
              <span className="badge">{r.id}</span>
              <span className="card__title">
                {formatMiles(r.distance_mi)} · {formatDuration(r.trip_h)}
              </span>
              {r.recommended && <span className="chip chip--rec">Recommended</span>}
              <span className="card__rank">#{r.rank}</span>
            </div>
            <div className="riskbar" aria-label="Miles by risk level">
              {RISK_KEYS.map((k) =>
                s.miles_by_level[k] > 0 ? (
                  <span key={k} style={{ width: `${(100 * s.miles_by_level[k]) / total}%`, background: RISK_COLOR[k] }} title={`${RISK_LABEL[k]}: ${s.miles_by_level[k].toFixed(0)} mi`} />
                ) : null,
              )}
            </div>
            <dl className="card__stats">
              <div>
                <dt>Severe</dt>
                <dd>{s.miles_by_level.severe.toFixed(0)} mi</dd>
              </div>
              <div>
                <dt>High</dt>
                <dd>{s.miles_by_level.high.toFixed(0)} mi</dd>
              </div>
              <div>
                <dt>No Travel</dt>
                <dd className={s.miles_by_level.no_travel > 0 ? 'bad' : ''}>{s.miles_by_level.no_travel.toFixed(0)} mi</dd>
              </div>
              <div>
                <dt>Avg risk</dt>
                <dd>{s.avg_risk.toFixed(2)} / 4</dd>
              </div>
              <div>
                <dt>Driving</dt>
                <dd>{formatDuration(r.driving_h)}</dd>
              </div>
              <div>
                <dt>Arrive</dt>
                <dd>{formatTime(r.arrival)}</dd>
              </div>
            </dl>
            {r.stops.length > 0 && (
              <div className="card__note">
                Includes {r.stops.filter((x) => x.type === 'break').length} × 30-min break, {r.stops.filter((x) => x.type === 'rest').length} × 10-h rest
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}
