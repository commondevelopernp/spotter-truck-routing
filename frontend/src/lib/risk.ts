import type { HeatLayerKey, RiskKey } from '../types'

export const RISK_KEYS: RiskKey[] = ['low', 'moderate', 'high', 'severe', 'no_travel']

export const RISK_LABEL: Record<RiskKey, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
}

export const RISK_COLOR: Record<RiskKey, string> = {
  low: '#16a34a',
  moderate: '#eab308',
  high: '#f97316',
  severe: '#dc2626',
  no_travel: '#7e22ce',
}

const RGB: [number, number, number][] = RISK_KEYS.map((k) => {
  const hex = RISK_COLOR[k]
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]
})

/** Band edges per metric, mirroring the assessment's risk table (Low→Moderate→High→Severe→No Travel).
 * Used only for colouring the heatmap; the authoritative classification runs on the server. */
export const HEAT_SCALES: Record<Exclude<HeatLayerKey, 'risk'>, { edges: number[]; unit: string; label: string }> = {
  wind: { edges: [0, 25, 35, 45, 55], unit: 'mph', label: 'Wind' },
  rain: { edges: [0, 0.1, 0.25, 0.5, 1.0], unit: 'in/hr', label: 'Rain' },
  snow: { edges: [0, 0.5, 1.0, 2.0, 3.0], unit: 'in/hr', label: 'Snow' },
}

/** Map a raw value onto a continuous 0–4 "level" so every layer shares one colour ramp. */
export function toLevel(layer: HeatLayerKey, value: number): number {
  if (layer === 'risk') return value
  const e = HEAT_SCALES[layer].edges
  if (value <= e[0]) return 0
  for (let i = 1; i < e.length; i++) {
    if (value < e[i]) return i - 1 + (value - e[i - 1]) / (e[i] - e[i - 1])
  }
  return 4
}

/** RGBA for a continuous level. Calm areas stay faint so the base map stays readable. */
export function levelColor(level: number): string {
  const l = Math.max(0, Math.min(4, level))
  const i = Math.min(3, Math.floor(l))
  const t = l - i
  const a = RGB[i]
  const b = RGB[i + 1]
  const r = Math.round(a[0] + (b[0] - a[0]) * t)
  const g = Math.round(a[1] + (b[1] - a[1]) * t)
  const bl = Math.round(a[2] + (b[2] - a[2]) * t)
  const alpha = l < 1 ? 0.1 + 0.35 * l : Math.min(0.8, 0.45 + 0.1 * (l - 1))
  return `rgba(${r},${g},${bl},${alpha.toFixed(3)})`
}
