import type { Venue } from '../../../../../contracts/protocol.ts'

/**
 * Approved public venue allowlist, copied from server/planning/data/venues.json
 * (equal to contracts/fixtures/venues.json). The server only accepts M7 output
 * that names one of these placeIds; the card only renders a venue found here.
 * tests/planning/test_web_venues.py fails if this copy drifts.
 */
export const APPROVED_VENUES: readonly Venue[] = [
  { placeId: 'v-cafe', name: 'Campus Cafe', kind: 'cafe', isPublic: true },
  { placeId: 'v-dining-north', name: 'North Dining Hall', kind: 'dining_hall', isPublic: true },
  { placeId: 'v-library-commons', name: 'Library Commons', kind: 'library', isPublic: true },
  { placeId: 'v-quad', name: 'Main Quad', kind: 'park', isPublic: true },
  { placeId: 'v-rec', name: 'Rec Center Courts', kind: 'rec_center', isPublic: true },
]

/** Approved campus events (same file). Activity signals and event heat may count only these ids. */
export interface ApprovedEvent {
  eventId: string
  title: string
  placeId: string
  start: string
}

export const APPROVED_EVENTS: readonly ApprovedEvent[] = [
  { eventId: 'ev-open-mic', title: 'Open mic night', placeId: 'v-cafe', start: '2026-11-19T03:00:00Z' },
  { eventId: 'ev-volleyball', title: 'Pickup volleyball', placeId: 'v-rec', start: '2026-11-18T23:00:00Z' },
  { eventId: 'ev-board-games', title: 'Board game night', placeId: 'v-library-commons', start: '2026-11-20T01:00:00Z' },
  { eventId: 'ev-film-club', title: 'Film club screening', placeId: 'v-quad', start: '2026-11-21T02:00:00Z' },
]

export function eventFor(eventId: string): ApprovedEvent | null {
  return APPROVED_EVENTS.find((event) => event.eventId === eventId) ?? null
}

export function venueFor(placeId: string, venues: readonly Venue[] = APPROVED_VENUES): Venue | null {
  return venues.find((venue) => venue.placeId === placeId && venue.isPublic === true) ?? null
}
