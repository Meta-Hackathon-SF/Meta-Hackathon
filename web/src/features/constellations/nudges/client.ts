import type { EventNudge } from '../../../../../contracts/protocol.ts'
import { parseEventNudge } from './parse.ts'

/**
 * Client for POST /operator/rooms/:id/nudge (contracts/API.md). The session is
 * the server's cookie; this never sends a playerId. Operator-only: the server
 * checks the operator role, this client does not grant anything.
 */

export class NudgeRequestError extends Error {
  readonly code: string
  readonly retryable: boolean

  constructor(code: string, message: string, retryable: boolean) {
    super(message)
    this.name = 'NudgeRequestError'
    this.code = code
    this.retryable = retryable
  }
}

/** Ask the server to propose and post one nudge for a room. Resolves with the validated EventNudge. */
export type NudgeRequester = (roomId: string, signal?: AbortSignal) => Promise<EventNudge>

function errorFrom(payload: unknown, status: number): NudgeRequestError {
  const error = (payload as { error?: Record<string, unknown> } | null)?.error
  const code = typeof error?.code === 'string' && /^[A-Z_]{1,40}$/.test(error.code) ? error.code : `HTTP_${status}`
  // Only code-chosen messages are shown; the server's free text is not echoed.
  const retryable = error?.retryable === true
  return new NudgeRequestError(code, MESSAGES[code] ?? 'The nudge could not be posted.', retryable)
}

export const MESSAGES: Record<string, string> = {
  NOT_FOUND: 'That room is closed or too small for a nudge.',
  PROVIDER_UNAVAILABLE: 'Muse had no safe suggestion this time. Nothing was posted.',
  UNAUTHORIZED: 'Sign in as the operator first.',
  FORBIDDEN: 'Only the operator can post a nudge.',
  INVALID_INPUT: 'That room id is not valid.',
  BAD_RESPONSE: 'The server sent a nudge that did not pass validation. Nothing is shown.',
  NETWORK: 'The server could not be reached.',
}

export function createNudgeRequester(base: string): NudgeRequester {
  return async (roomId, signal) => {
    let response: Response
    try {
      response = await fetch(`${base}/operator/rooms/${encodeURIComponent(roomId)}/nudge`, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        credentials: 'include',
        signal,
      })
    } catch (error) {
      if ((error as Error)?.name === 'AbortError') throw error
      throw new NudgeRequestError('NETWORK', MESSAGES.NETWORK, true)
    }
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }
    if (!response.ok) throw errorFrom(payload, response.status)
    const nudge = parseEventNudge(payload)
    if (!nudge) throw new NudgeRequestError('BAD_RESPONSE', MESSAGES.BAD_RESPONSE, false)
    return nudge
  }
}
