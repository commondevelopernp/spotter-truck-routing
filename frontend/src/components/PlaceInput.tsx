import { useEffect, useId, useRef, useState } from 'react'
import { searchPlaces } from '../api'
import type { Place } from '../types'

interface Props {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  error?: string
}

/** Text input with debounced geocoder suggestions. Free text is always accepted;
 * the server geocodes whatever is submitted (or "lat, lon" pairs). */
export default function PlaceInput({ label, value, onChange, placeholder, error }: Props) {
  const id = useId()
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const skipNext = useRef(false)

  useEffect(() => {
    if (skipNext.current) {
      skipNext.current = false
      return
    }
    if (value.trim().length < 3) {
      setResults([])
      return
    }
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      searchPlaces(value, ctrl.signal)
        .then((r) => {
          setResults(r)
          setActive(-1)
        })
        .catch(() => setResults([]))
    }, 300)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [value])

  const pick = (p: Place) => {
    skipNext.current = true
    onChange(p.name)
    setOpen(false)
  }

  return (
    <div className="field place">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        aria-invalid={!!error}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (!open || !results.length) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((a) => (a + 1) % results.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((a) => (a <= 0 ? results.length - 1 : a - 1))
          } else if (e.key === 'Enter' && active >= 0) {
            e.preventDefault()
            pick(results[active])
          } else if (e.key === 'Escape') setOpen(false)
        }}
      />
      {open && results.length > 0 && (
        <ul className="suggestions" role="listbox">
          {results.map((r, i) => (
            <li key={`${r.lat},${r.lon}`} role="option" aria-selected={i === active} className={i === active ? 'active' : ''} onMouseDown={() => pick(r)}>
              {r.name}
            </li>
          ))}
        </ul>
      )}
      {error && <div className="field-error">{error}</div>}
    </div>
  )
}
