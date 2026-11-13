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

export function venueFor(placeId: string, venues: readonly Venue[] = APPROVED_VENUES): Venue | null {
  return venues.find((venue) => venue.placeId === placeId && venue.isPublic === true) ?? null
}
