import L from 'leaflet'

/**
 * Minimal Leaflet layer that paints one coloured cell per corridor grid point on a
 * single <canvas>. Changing the forecast hour only repaints the canvas (a few hundred
 * fillRect calls) — no DOM nodes or React reconciliation — which keeps the slider at 60 fps.
 * The soft "heatmap" look comes from a GPU-accelerated CSS blur on the canvas.
 */
export class HeatCanvasLayer extends L.Layer {
  private canvas?: HTMLCanvasElement
  private points: [number, number][] = []
  private halfLat = 0
  private halfLon = 0
  private colors: string[] = []
  private frame = 0

  setGrid(points: [number, number][], cellLat: number, cellLon: number) {
    this.points = points
    this.halfLat = cellLat / 2
    this.halfLon = cellLon / 2
    this.schedule()
  }

  setColors(colors: string[]) {
    this.colors = colors
    this.schedule()
  }

  onAdd(map: L.Map) {
    this.canvas = L.DomUtil.create('canvas', 'heat-canvas leaflet-zoom-hide') as HTMLCanvasElement
    let pane = map.getPane('heat')
    if (!pane) {
      pane = map.createPane('heat')
      pane.style.zIndex = '350' // above tiles (200), below vector overlays (400)
      pane.style.pointerEvents = 'none'
    }
    pane.appendChild(this.canvas)
    map.on('moveend zoomend resize viewreset', this.reset, this)
    this.reset()
    return this
  }

  onRemove(map: L.Map) {
    map.off('moveend zoomend resize viewreset', this.reset, this)
    this.canvas?.remove()
    this.canvas = undefined
    cancelAnimationFrame(this.frame)
    return this
  }

  private reset() {
    const map = this._map
    if (!map || !this.canvas) return
    const size = map.getSize()
    const dpr = window.devicePixelRatio || 1
    this.canvas.width = size.x * dpr
    this.canvas.height = size.y * dpr
    this.canvas.style.width = `${size.x}px`
    this.canvas.style.height = `${size.y}px`
    L.DomUtil.setPosition(this.canvas, map.containerPointToLayerPoint([0, 0]))
    this.draw()
  }

  private schedule() {
    cancelAnimationFrame(this.frame)
    this.frame = requestAnimationFrame(() => this.draw())
  }

  private draw() {
    const map = this._map
    const canvas = this.canvas
    if (!map || !canvas) return
    const ctx = canvas.getContext('2d')!
    const dpr = window.devicePixelRatio || 1
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!this.colors.length) return
    let cellPx = 0
    for (let i = 0; i < this.points.length; i++) {
      const [lat, lon] = this.points[i]
      const nw = map.latLngToContainerPoint([lat + this.halfLat, lon - this.halfLon])
      const se = map.latLngToContainerPoint([lat - this.halfLat, lon + this.halfLon])
      ctx.fillStyle = this.colors[i]
      // +1 px overlap avoids hairline seams between neighbouring cells.
      ctx.fillRect(nw.x, nw.y, se.x - nw.x + 1, se.y - nw.y + 1)
      cellPx = se.x - nw.x
    }
    canvas.style.filter = `blur(${Math.max(2, Math.min(24, cellPx * 0.45)).toFixed(1)}px)`
  }
}
