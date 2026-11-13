import { MapPin, Users } from 'lucide-react'
import type { EventNudge, Venue } from '../../../../../contracts/protocol.ts'
import { formatLatency, formatWindow } from './format.ts'
import styles from './nudges.module.css'

export interface NudgeCardProps {
  nudge: EventNudge
  /** The approved venue for nudge.placeId. Without it the card does not render. */
  venue: Venue | null
  /** Community time zone, e.g. "America/Los_Angeles". Defaults to the viewer's. */
  timeZone?: string
  /** Operator views pass true to show the model, call type and latency. */
  showEvidence?: boolean
}

/**
 * Event nudge shown inside a constellation's chat (Kai places it).
 * Display only: it never offers a way to trade contact details and never
 * names what the group has in common.
 */
export function NudgeCard({ nudge, venue, timeZone, showEvidence = false }: NudgeCardProps) {
  if (!venue || venue.placeId !== nudge.placeId || venue.isPublic !== true) return null
  const replay = nudge.evidence.source === 'replay'

  return (
    <article className={styles.card} aria-label={`Muse suggests: ${nudge.title}`}>
      <p className={styles.eyebrow}>Muse suggests</p>
      <h3 className={styles.title}>{nudge.title}</h3>
      <p className={styles.when}>{formatWindow(nudge.timeWindow, timeZone)}</p>
      <p className={styles.place}>
        <MapPin size={15} aria-hidden="true" />
        <span>{venue.name}</span>
        <span className={styles.tag}>Public place</span>
      </p>
      <p className={styles.why}>{nudge.why}</p>
      <p className={styles.threshold}>
        <Users size={15} aria-hidden="true" />
        <span>Go if {nudge.minAttendees} of you are in.</span>
      </p>
      {(replay || showEvidence) && (
        <p className={styles.evidence}>
          {replay && <span className={styles.replay}>Replay of a saved cycle</span>}
          {showEvidence && (
            <span>
              {nudge.evidence.callType} · {nudge.evidence.model} · {formatLatency(nudge.evidence.latencyMs)}
            </span>
          )}
        </p>
      )}
    </article>
  )
}
