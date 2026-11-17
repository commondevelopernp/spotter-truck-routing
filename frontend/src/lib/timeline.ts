import type { Checkpoint } from '../types'

/** Mile reached at time `tMs`, interpolating between checkpoint ETAs.
 * Returns null before departure; clamps to the last checkpoint after arrival. */
export function mileAt(checkpoints: Checkpoint[], tMs: number): number | null {
  if (!checkpoints.length) return null
  const times = checkpoints.map((c) => Date.parse(c.eta))
  if (tMs < times[0]) return null
  const last = checkpoints.length - 1
  if (tMs >= times[last]) return checkpoints[last].mile
  for (let i = 0; i < last; i++) {
    if (tMs < times[i + 1]) {
      const span = times[i + 1] - times[i]
      const f = span ? (tMs - times[i]) / span : 0
      return checkpoints[i].mile + (checkpoints[i + 1].mile - checkpoints[i].mile) * f
    }
  }
  return checkpoints[last].mile
}

/** Split the route into stretches owned by each checkpoint (half the gap on each side),
 * matching how the server attributes miles to risk levels. */
export function ownedStretches(checkpoints: Checkpoint[]): { from: number; to: number; cp: Checkpoint }[] {
  return checkpoints.map((cp, i) => {
    const from = i === 0 ? cp.mile : (checkpoints[i - 1].mile + cp.mile) / 2
    const to = i === checkpoints.length - 1 ? cp.mile : (cp.mile + checkpoints[i + 1].mile) / 2
    return { from, to, cp }
  })
}
