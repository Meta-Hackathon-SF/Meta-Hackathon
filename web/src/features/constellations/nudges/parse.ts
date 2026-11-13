import type { EventNudge, MuseCallEvidence, Venue } from '../../../../../contracts/protocol.ts'

/**
 * Runtime validation for an EventNudge received from the server.
 * TypeScript types are not validation: anything that does not match the
 * 2.0.0 contract exactly is dropped and the card is not rendered.
 */

const CALL_TYPES = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9', 'M10']
const VENUE_KINDS = ['cafe', 'dining_hall', 'library', 'park', 'rec_center', 'campus_event']
const UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown, max: number): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= max
}

function utc(value: unknown): value is string {
  return typeof value === 'string' && UTC.test(value) && !Number.isNaN(Date.parse(value))
}

function parseEvidence(value: unknown): MuseCallEvidence | null {
  if (!isRecord(value)) return null
  const { model, source, generatedAt, latencyMs, callType } = value
  if (!text(model, 80)) return null
  if (source !== 'live' && source !== 'replay') return null
  if (!utc(generatedAt)) return null
  if (typeof latencyMs !== 'number' || !Number.isFinite(latencyMs) || latencyMs < 0) return null
  if (typeof callType !== 'string' || !CALL_TYPES.includes(callType)) return null
  return { model, source, generatedAt, latencyMs, callType: callType as MuseCallEvidence['callType'] }
}

export function parseEventNudge(value: unknown): EventNudge | null {
  if (!isRecord(value)) return null
  const { nudgeId, constellationId, title, placeId, timeWindow, why, minAttendees } = value
  if (!text(nudgeId, 80) || !text(constellationId, 80) || !text(placeId, 64)) return null
  if (!text(title, 80) || !text(why, 240)) return null
  if (minAttendees !== 3) return null
  if (!isRecord(timeWindow) || !utc(timeWindow.start) || !utc(timeWindow.end)) return null
  if (Date.parse(timeWindow.end) <= Date.parse(timeWindow.start)) return null
  const evidence = parseEvidence(value.evidence)
  if (!evidence) return null
  return {
    nudgeId,
    constellationId,
    title,
    placeId,
    timeWindow: { start: timeWindow.start, end: timeWindow.end },
    why,
    minAttendees,
    evidence,
  }
}

/** Only an approved, public venue is ever shown. Anything else returns null. */
export function parseVenue(value: unknown): Venue | null {
  if (!isRecord(value)) return null
  const { placeId, name, kind, isPublic } = value
  if (!text(placeId, 64) || !text(name, 80)) return null
  if (typeof kind !== 'string' || !VENUE_KINDS.includes(kind)) return null
  if (isPublic !== true) return null
  return { placeId, name, kind: kind as Venue['kind'], isPublic }
}
