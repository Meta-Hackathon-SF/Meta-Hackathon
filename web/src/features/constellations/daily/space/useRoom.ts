/*
 * Live anonymous room for the Space chat screen. Backed by the real LiveChatSession (server room,
 * SSE stream, moderated messages, mutual reveal). No local state stands in for the server: without
 * VITE_CONSTELLATIONS_API there is no room, and the screen says so.
 */
import { useEffect, useMemo, useSyncExternalStore } from "react";
import { createChatClient } from "../../chat/client";
import { LiveChatSession } from "../../chat/LiveSession";
import type { LiveSnapshot } from "../../chat/LiveSession";
import type { ChatActions } from "../../chat/ChatPanel";

const BASE = (import.meta.env.VITE_CONSTELLATIONS_API as string | undefined)?.replace(/\/$/, "");
const NONE: LiveSnapshot = { messages: [], reveals: [], status: "unavailable", notice: "Chat needs the live server." };
const noop = () => () => {};

export interface RoomHandle {
  snapshot: LiveSnapshot;
  actions: ChatActions | null;
  live: boolean;
}

export function useRoom(cycleId: string, viewerPlayerId: string, enabled: boolean): RoomHandle {
  const session = useMemo(
    () => (BASE && enabled ? new LiveChatSession(createChatClient({ baseUrl: BASE }), cycleId, viewerPlayerId) : null),
    [cycleId, viewerPlayerId, enabled],
  );
  useEffect(() => {
    session?.start();
    return () => session?.stop();
  }, [session]);
  const snapshot = useSyncExternalStore(session?.subscribe ?? noop, session?.getSnapshot ?? (() => NONE), () => NONE);
  const roomId = snapshot.room?.roomId;
  const actions = useMemo(() => (session && roomId ? session.actions(roomId) : null), [session, roomId]);
  return { snapshot, actions, live: session !== null };
}
