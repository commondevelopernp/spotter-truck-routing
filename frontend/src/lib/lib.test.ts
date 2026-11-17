import { describe, expect, it } from 'vitest'
import { cumulativeMiles, pointAtMile, slice } from './geo'
import { levelColor, toLevel } from './risk'
import { mileAt, ownedStretches } from './timeline'
import type { Checkpoint } from '../types'

const cp = (mile: number, eta: string): Checkpoint => ({
  mile,
  lat: 0,
  lon: 0,
  eta,
  weather: { wind_mph: 0, gust_mph: 0, rain_in_hr: 0, snow_in_hr: 0 },
  risk: { level: 'low', label: 'Low', score: 0, reasons: [] },
})

describe('heat scales follow the risk table', () => {
  it('maps band edges to whole levels', () => {
    expect(toLevel('wind', 25)).toBe(1)
    expect(toLevel('wind', 55)).toBe(4)
    expect(toLevel('rain', 0.25)).toBe(2)
    expect(toLevel('snow', 2.0)).toBe(3)
    expect(toLevel('wind', 30)).toBeCloseTo(1.5)
  })
  it('keeps calm cells faint', () => {
    expect(levelColor(0)).toMatch(/0\.100\)$/)
  })
})

describe('timeline', () => {
  const cps = [cp(0, '2026-01-01T00:00:00Z'), cp(50, '2026-01-01T01:00:00Z'), cp(60, '2026-01-01T11:00:00Z')]
  it('interpolates mile by time', () => {
    expect(mileAt(cps, Date.parse('2026-01-01T00:30:00Z'))).toBe(25)
    expect(mileAt(cps, Date.parse('2026-01-01T06:00:00Z'))).toBe(55)
  })
  it('is null before departure and clamps after arrival', () => {
    expect(mileAt(cps, Date.parse('2025-12-31T23:00:00Z'))).toBeNull()
    expect(mileAt(cps, Date.parse('2026-01-02T00:00:00Z'))).toBe(60)
  })
  it('owned stretches tile the route', () => {
    const s = ownedStretches(cps)
    expect(s.map((x) => [x.from, x.to])).toEqual([[0, 25], [25, 55], [55, 60]])
  })
})

describe('geo', () => {
  const line: [number, number][] = [[0, 0], [0, 1], [0, 2]]
  it('rescales to server distance and finds points', () => {
    const cum = cumulativeMiles(line, 100)
    expect(cum[2]).toBeCloseTo(100)
    expect(pointAtMile(line, cum, 75)[1]).toBeCloseTo(1.5)
    const part = slice(line, cum, 25, 75)
    expect(part[0][1]).toBeCloseTo(0.5)
    expect(part[part.length - 1][1]).toBeCloseTo(1.5)
    expect(part).toHaveLength(3)
  })
})
