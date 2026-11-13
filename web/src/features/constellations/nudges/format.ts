import type { TimeWindow } from '../../../../../contracts/protocol.ts'

/** "Wednesday 7pm-9pm" in the community time zone (the viewer's zone when omitted). */
export function formatWindow(window: TimeWindow, timeZone?: string): string {
  const day = new Intl.DateTimeFormat('en-US', { weekday: 'long', timeZone })
  return `${day.format(new Date(window.start))} ${clock(window.start, timeZone)}-${clock(window.end, timeZone)}`
}

function clock(iso: string, timeZone?: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone,
  }).formatToParts(new Date(iso))
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  const minutes = get('minute') === '00' ? '' : `:${get('minute')}`
  return `${get('hour')}${minutes}${get('dayPeriod').toLowerCase()}`
}

export function formatLatency(latencyMs: number): string {
  return latencyMs >= 1000 ? `${(latencyMs / 1000).toFixed(1)} s` : `${Math.round(latencyMs)} ms`
}
