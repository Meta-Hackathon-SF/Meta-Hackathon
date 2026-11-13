import { useEffect, useRef, useState } from 'react'
import type { EventNudge, Venue } from '../../../../../contracts/protocol.ts'
import { MESSAGES, NudgeRequestError, type NudgeRequester } from './client.ts'
import { NudgeCard } from './NudgeCard.tsx'
import { APPROVED_VENUES, venueFor } from './venues.ts'
import styles from './nudges.module.css'

export interface OperatorNudgePanelProps {
  /** Open constellation room to nudge. */
  roomId: string
  /** Server call; use createNudgeRequester(base) live. */
  request: NudgeRequester
  venues?: readonly Venue[]
  timeZone?: string
}

type State =
  | { status: 'idle' }
  | { status: 'busy' }
  | { status: 'posted'; nudge: EventNudge }
  | { status: 'error'; message: string; retryable: boolean }

/**
 * Operator demo button: Muse proposes one event nudge for a room, the server
 * validates and guards it and posts it as a `muse_nudge` message. The panel
 * shows what was posted, with model evidence. Stale or cancelled responses are
 * ignored. It never shows a nudge whose venue is not on the approved list.
 */
export function OperatorNudgePanel(props: OperatorNudgePanelProps) {
  // A new room remounts the panel: the call in flight is cancelled and its result forgotten.
  return <Panel key={props.roomId} {...props} />
}

function Panel({ roomId, request, venues = APPROVED_VENUES, timeZone }: OperatorNudgePanelProps) {
  const [state, setState] = useState<State>({ status: 'idle' })
  const current = useRef<AbortController | null>(null)

  useEffect(() => () => {
    current.current?.abort()
    current.current = null
  }, [])

  async function post() {
    if (state.status === 'busy') return
    current.current?.abort()
    const controller = new AbortController()
    current.current = controller
    setState({ status: 'busy' })
    try {
      const nudge = await request(roomId, controller.signal)
      if (current.current !== controller) return
      if (!venueFor(nudge.placeId, venues)) {
        setState({ status: 'error', message: MESSAGES.BAD_RESPONSE, retryable: false })
        return
      }
      setState({ status: 'posted', nudge })
    } catch (error) {
      if (current.current !== controller || (error as Error)?.name === 'AbortError') return
      const known = error instanceof NudgeRequestError
      setState({
        status: 'error',
        message: known ? error.message : MESSAGES.NETWORK,
        retryable: known ? error.retryable : true,
      })
    } finally {
      if (current.current === controller) current.current = null
    }
  }

  const busy = state.status === 'busy'
  return (
    <section className={styles.panel} aria-label="Event nudge">
      <div className={styles.panelHead}>
        <h3 className={styles.panelTitle}>Event nudge</h3>
        <button type="button" className={styles.panelButton} onClick={post} disabled={busy} aria-busy={busy}>
          {busy ? 'Asking Muse...' : state.status === 'posted' ? 'Post again' : 'Post event nudge'}
        </button>
      </div>
      <p className={styles.panelHint}>
        Muse suggests one public place and time. The server checks the venue, the time and the text before it posts
        to the room. Posting twice in a week reuses the first nudge.
      </p>
      <div aria-live="polite">
        {state.status === 'posted' && (
          <>
            <p className={styles.panelStatus}>Posted to the room as a Muse message.</p>
            <NudgeCard nudge={state.nudge} venue={venueFor(state.nudge.placeId, venues)} timeZone={timeZone} showEvidence />
          </>
        )}
        {state.status === 'error' && (
          <p className={styles.panelError} role="alert">
            {state.message}
            {state.retryable ? ' You can try again.' : ''}
          </p>
        )}
      </div>
    </section>
  )
}
