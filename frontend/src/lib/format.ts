const timeFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
const tzName =
  new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(new Date()).find((p) => p.type === 'timeZoneName')?.value ?? ''

export const formatTime = (iso: string | number) => timeFmt.format(new Date(iso))
export const timeZoneLabel = tzName

export function formatDuration(hours: number): string {
  const total = Math.round(hours * 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h} h ${m.toString().padStart(2, '0')} min` : `${m} min`
}

export const formatMiles = (mi: number) => `${Math.round(mi).toLocaleString()} mi`

/** Value for <input type="datetime-local"> from a Date, in the browser's time zone. */
export function toLocalInput(d: Date): string {
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}
