/*
 * Revealed connections (Simulated Facebook). Only a mutual reveal puts someone here. Chat text expires with
 * the room; this store does not, so the revealed person and "Request sent" survive chat expiry.
 */
import { useSyncExternalStore } from "react";

export interface Connection {
  id: string;
  name: string;
  requested: boolean;
}

const KEY = "spc-connections-v1";
const listeners = new Set<() => void>();

function load(): Connection[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((c) => c && typeof c.id === "string" && typeof c.name === "string") : [];
  } catch {
    return [];
  }
}

let state: Connection[] = load();

function commit(next: Connection[]) {
  state = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable */
  }
  listeners.forEach((l) => l());
}

export function ensureConnection(id: string, name: string) {
  if (!state.some((c) => c.id === id)) commit([...state, { id, name, requested: false }]);
}

export function sendFriendRequest(id: string, name: string) {
  const has = state.some((c) => c.id === id);
  commit(has ? state.map((c) => (c.id === id ? { ...c, requested: true } : c)) : [...state, { id, name, requested: true }]);
}

export function useConnections(): Connection[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
  );
}
