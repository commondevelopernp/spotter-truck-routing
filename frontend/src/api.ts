import type { HeatmapResponse, PlanRequest, PlanResponse, Place } from './types'

export class ApiError extends Error {
  field?: string
  fields?: Record<string, string[]>
  constructor(message: string, field?: string, fields?: Record<string, string[]>) {
    super(message)
    this.field = field
    this.fields = fields
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError('Network error — check your connection and retry.')
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const fields = body.fields as Record<string, string[]> | undefined
    const first = fields ? Object.entries(fields)[0] : undefined
    const message = first ? `${first[0].replace('_', ' ')}: ${first[1][0]}` : body.error || `Request failed (${res.status})`
    throw new ApiError(message, body.field ?? first?.[0], fields)
  }
  return body as T
}

export const planTrip = (req: PlanRequest, signal?: AbortSignal) =>
  request<PlanResponse>('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })

export const fetchHeatmap = (planId: string, signal?: AbortSignal) =>
  request<HeatmapResponse>(`/api/heatmap/${planId}`, { signal })

export const searchPlaces = (q: string, signal?: AbortSignal) =>
  request<{ results: Place[] }>(`/api/geocode?q=${encodeURIComponent(q)}`, { signal }).then((r) => r.results)
