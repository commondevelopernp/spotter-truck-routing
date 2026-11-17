export type LatLng = [number, number]

const R_MI = 3958.8
const rad = (d: number) => (d * Math.PI) / 180

export function haversineMi(a: LatLng, b: LatLng): number {
  const dLat = rad(b[0] - a[0])
  const dLon = rad(b[1] - a[1])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2
  return 2 * R_MI * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** Cumulative miles along a polyline, rescaled so the last value equals `totalMi`
 * (the routing API's distance), keeping map positions consistent with server miles. */
export function cumulativeMiles(points: LatLng[], totalMi?: number): number[] {
  const out = [0]
  for (let i = 1; i < points.length; i++) out.push(out[i - 1] + haversineMi(points[i - 1], points[i]))
  const raw = out[out.length - 1]
  if (totalMi && raw > 0) {
    const k = totalMi / raw
    for (let i = 0; i < out.length; i++) out[i] *= k
  }
  return out
}

function lowerIndex(cum: number[], mile: number): number {
  let lo = 0
  let hi = cum.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (cum[mid] <= mile) lo = mid
    else hi = mid
  }
  return lo
}

export function pointAtMile(points: LatLng[], cum: number[], mile: number): LatLng {
  if (mile <= 0) return points[0]
  if (mile >= cum[cum.length - 1]) return points[points.length - 1]
  const i = lowerIndex(cum, mile)
  const seg = cum[i + 1] - cum[i]
  const t = seg ? (mile - cum[i]) / seg : 0
  return [points[i][0] + (points[i + 1][0] - points[i][0]) * t, points[i][1] + (points[i + 1][1] - points[i][1]) * t]
}

/** Slice a polyline between two mile marks (inclusive interpolated endpoints). */
export function slice(points: LatLng[], cum: number[], from: number, to: number): LatLng[] {
  const out: LatLng[] = [pointAtMile(points, cum, from)]
  for (let i = 0; i < points.length; i++) {
    if (cum[i] > from && cum[i] < to) out.push(points[i])
  }
  out.push(pointAtMile(points, cum, to))
  return out
}
