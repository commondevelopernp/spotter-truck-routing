export type RiskKey = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'

export interface Place {
  name: string
  lat: number
  lon: number
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta: string
  weather: { wind_mph: number; gust_mph: number; rain_in_hr: number; snow_in_hr: number }
  risk: { level: RiskKey; label: string; score: number; reasons: string[] }
}

export interface HosStop {
  type: 'break' | 'rest'
  after_driving_h: number
  duration_h: number
}

export interface RouteSummary {
  distance_mi: number
  duration_h: number
  miles_by_level: Record<RiskKey, number>
  avg_risk: number
  max_level: RiskKey
}

export interface RouteOption {
  id: string
  rank: number
  recommended: boolean
  source: 'osrm' | 'via'
  geometry: [number, number][]
  distance_mi: number
  driving_h: number
  trip_h: number
  arrival: string
  stops: HosStop[]
  summary: RouteSummary
  checkpoints: Checkpoint[]
}

export interface PlanResponse {
  plan_id: string
  origin: Place
  destination: Place
  departure: string
  load_lbs: number
  interval_mi: 10 | 25 | 50
  hos: boolean
  routes: RouteOption[]
  recommendation: { route_id: string; reason: string; all_no_travel: boolean }
  corridor: { cell_mi: number; buffer_mi: number; count: number }
}

export type HeatLayerKey = 'risk' | 'wind' | 'rain' | 'snow'

export interface HeatmapResponse {
  plan_id: string
  start: string
  hours: number
  points: [number, number][]
  cell_lat_deg: number
  cell_lon_deg: number
  cell_mi: number
  layers: Record<HeatLayerKey, number[][]>
}

export interface PlanRequest {
  origin: string
  destination: string
  departure: string
  load_lbs: number
  interval_mi: 10 | 25 | 50
  hos: boolean
}
