import { useEffect, useMemo, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { HeatCanvasLayer } from '../lib/heatCanvas'
import { levelColor, toLevel } from '../lib/risk'
import type { HeatLayerKey, HeatmapResponse } from '../types'

interface Props {
  data: HeatmapResponse
  layer: HeatLayerKey
  hour: number // fractional hours since data.start
  visible: boolean
}

export default function HeatmapLayer({ data, layer, hour, visible }: Props) {
  const map = useMap()
  const ref = useRef<HeatCanvasLayer | null>(null)

  useEffect(() => {
    const l = new HeatCanvasLayer()
    ref.current = l
    l.addTo(map)
    return () => {
      l.remove()
      ref.current = null
    }
  }, [map])

  useEffect(() => {
    ref.current?.setGrid(data.points, data.cell_lat_deg, data.cell_lon_deg)
  }, [data])

  // Pre-convert every frame to 0–4 levels once per layer switch; per-tick work is then a lerp.
  const levels = useMemo(() => data.layers[layer].map((frame) => frame.map((v) => toLevel(layer, v))), [data, layer])

  useEffect(() => {
    if (!ref.current) return
    if (!visible) {
      ref.current.setColors([])
      return
    }
    const max = levels.length - 1
    const h = Math.max(0, Math.min(max, hour))
    const i = Math.min(max - 1, Math.floor(h))
    const t = h - i
    const a = levels[i]
    const b = levels[i + 1] ?? a
    ref.current.setColors(a.map((v, k) => levelColor(v + (b[k] - v) * t)))
  }, [levels, hour, visible])

  return null
}
