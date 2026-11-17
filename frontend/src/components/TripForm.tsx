import { useState, type FormEvent } from 'react'
import { toLocalInput } from '../lib/format'
import type { PlanRequest } from '../types'
import PlaceInput from './PlaceInput'

interface Props {
  loading: boolean
  onSubmit: (req: PlanRequest) => void
  fieldError?: { field?: string; message: string } | null
}

const nextHour = () => {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  return d
}

export default function TripForm({ loading, onSubmit, fieldError }: Props) {
  const [origin, setOrigin] = useState('Chicago, Illinois')
  const [destination, setDestination] = useState('Denver, Colorado')
  const [departure, setDeparture] = useState(toLocalInput(nextHour()))
  const [load, setLoad] = useState('38000')
  const [interval, setSampleInterval] = useState<10 | 25 | 50>(25)
  const [hos, setHos] = useState(true)

  const min = toLocalInput(new Date())
  const max = toLocalInput(new Date(Date.now() + 7 * 86400_000))
  const err = (f: string) => (fieldError?.field === f ? fieldError.message : undefined)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit({
      origin,
      destination,
      departure: new Date(departure).toISOString(),
      load_lbs: Number(load),
      interval_mi: interval,
      hos,
    })
  }

  return (
    <form className="trip-form" onSubmit={submit}>
      <PlaceInput label="Origin" value={origin} onChange={setOrigin} placeholder="City, address or lat, lon" error={err('origin')} />
      <PlaceInput label="Destination" value={destination} onChange={setDestination} placeholder="City, address or lat, lon" error={err('destination')} />
      <div className="row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input id="departure" type="datetime-local" required value={departure} min={min} max={max} onChange={(e) => setDeparture(e.target.value)} />
          {err('departure') && <div className="field-error">{err('departure')}</div>}
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input id="load" type="number" required min={0} max={200000} step={500} value={load} onChange={(e) => setLoad(e.target.value)} />
          {err('load_lbs') && <div className="field-error">{err('load_lbs')}</div>}
        </div>
      </div>
      <div className="row row--center">
        <div className="field">
          <span className="label">Weather sample every</span>
          <div className="segmented" role="radiogroup" aria-label="Sampling interval">
            {([10, 25, 50] as const).map((v) => (
              <button type="button" key={v} role="radio" aria-checked={interval === v} className={interval === v ? 'on' : ''} onClick={() => setSampleInterval(v)}>
                {v} mi
              </button>
            ))}
          </div>
        </div>
        <label className="check" title="Adds a 30-min break after 8 h of driving and a 10-h rest after 11 h (FMCSA hours of service).">
          <input type="checkbox" checked={hos} onChange={(e) => setHos(e.target.checked)} /> HOS breaks
        </label>
      </div>
      <button className="primary" type="submit" disabled={loading}>
        {loading ? 'Planning routes…' : 'Find safest route'}
      </button>
    </form>
  )
}
