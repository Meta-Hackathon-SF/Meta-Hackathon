/*
 * Which star is which person, after mutual reveals (hosted app).
 *
 * The server's reveal.mutual event names the two players but not the star handle.
 * We remember which handles this player asked to reveal (sessionStorage, per room,
 * this tab only), and when a new reveal arrives we ask the server again about
 * those handles only. The one that now answers "revealed" is that person. We
 * never send a reveal request the player didn't make. If two reveals land at the
 * same moment and can't be told apart, the names still show as a list.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChatRoom, MutualReveal, Player } from "../../../../../../contracts/protocol";
import type { ChatActions } from "../../chat/ChatPanel";

const keyFor = (roomId: string) => `spc-reveal-asked:${roomId}`;
const namesKey = (roomId: string) => `spc-reveal-names:${roomId}`;

export function readAsked(roomId: string): string[] {
  try {
    const v = JSON.parse(sessionStorage.getItem(keyFor(roomId)) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/** Record a reveal request the player made (from the chat screen or Keep). */
export function rememberAsked(roomId: string, handle: string) {
  try {
    const all = new Set(readAsked(roomId)).add(handle);
    sessionStorage.setItem(keyFor(roomId), JSON.stringify([...all]));
  } catch {
    /* storage blocked: names still show as a list */
  }
}

function readNames(roomId: string): Record<string, Player> {
  try {
    const v = JSON.parse(sessionStorage.getItem(namesKey(roomId)) ?? "{}");
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

const key = () => `n-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export interface RoomNames {
  /** handle -> revealed player */
  names: Record<string, Player>;
  /** revealed people not matched to a handle yet */
  unplaced: Player[];
  asked: string[];
}

export function useRoomNames(room: ChatRoom | undefined, reveals: MutualReveal[], actions: ChatActions | null, viewerPlayerId: string): RoomNames {
  const roomId = room?.roomId ?? "";
  const [names, setNames] = useState<Record<string, Player>>(() => (roomId ? readNames(roomId) : {}));
  const others = useMemo(
    () =>
      reveals
        .filter((r) => r.roomId === roomId)
        .map((r) => r.players.find((p) => p.playerId !== viewerPlayerId))
        .filter((p): p is Player => Boolean(p)),
    [reveals, roomId, viewerPlayerId],
  );
  const placedIds = new Set(Object.values(names).map((p) => p.playerId));
  const unplaced = others.filter((p) => !placedIds.has(p.playerId));
  const busy = useRef(false);

  useEffect(() => {
    if (roomId) setNames(readNames(roomId));
  }, [roomId]);

  useEffect(() => {
    if (!actions || !roomId || busy.current || unplaced.length === 0) return;
    const pending = readAsked(roomId).filter((h) => !names[h] && room?.members.some((m) => m.handle === h));
    if (!pending.length) return;
    busy.current = true;
    void (async () => {
      const revealed: string[] = [];
      for (const handle of pending) {
        try {
          const r = (await actions.reveal(handle, { key: key(), signal: new AbortController().signal })) as { result?: string };
          if (r?.result === "revealed") revealed.push(handle);
        } catch {
          /* blocked or left */
        }
      }
      if (revealed.length === 1 && unplaced.length === 1) {
        const next = { ...names, [revealed[0]]: unplaced[0] };
        setNames(next);
        try {
          sessionStorage.setItem(namesKey(roomId), JSON.stringify(next));
        } catch {
          /* keep in memory */
        }
      }
      busy.current = false;
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actions, roomId, others.length]);

  return { names, unplaced, asked: roomId ? readAsked(roomId) : [] };
}
