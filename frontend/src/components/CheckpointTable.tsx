import { formatTime } from '../lib/format'
import { RISK_COLOR } from '../lib/risk'
import type { Checkpoint, RouteOption } from '../types'

export default function CheckpointTable({ route, onFocus }: { route: RouteOption; onFocus: (cp: Checkpoint) => void }) {
  return (
    <div className="table-wrap">
      <table className="cps">
        <thead>
          <tr>
            <th>Mile</th>
            <th>ETA</th>
            <th>Wind</th>
            <th>Rain</th>
            <th>Snow</th>
            <th>Risk</th>
          </tr>
        </thead>
        <tbody>
          {route.checkpoints.map((cp) => (
            <tr key={cp.mile} onClick={() => onFocus(cp)} title={cp.risk.reasons.join('; ') || 'Click to show on map'}>
              <td>{Math.round(cp.mile)}</td>
              <td>{formatTime(cp.eta)}</td>
              <td>{cp.weather.wind_mph.toFixed(0)} mph</td>
              <td>{cp.weather.rain_in_hr.toFixed(2)}</td>
              <td>{cp.weather.snow_in_hr.toFixed(2)}</td>
              <td>
                <span className="pill" style={{ background: RISK_COLOR[cp.risk.level] }}>
                  {cp.risk.label}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
