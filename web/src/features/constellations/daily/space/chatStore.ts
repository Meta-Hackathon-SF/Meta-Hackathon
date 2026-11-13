/*
 * Shared state for the 24-hour anonymous room, so it survives navigation: minimise to a
 * floating dock, and if everyone keeps it, move into Messenger. Starts empty; no
 * messages exist until a live chat source delivers them.
 *
 * open     -> room is live (24 h clock)
 * kept     -> everyone chose Keep before expiry; lives in Messenger
 * expired  -> clock ran out without everyone keeping it; the room is gone
 */
import { useSyncExternalStore } from "react";

export type ChatStatus = "none" | "open" | "kept" | "expired";
export interface ChatMsg {
  member?: number;
  mine?: boolean;
  text: string;
}
export interface ChatState {
  status: ChatStatus;
  minimized: boolean;
  msgs: ChatMsg[];
  keep: Record<string, boolean>;
  hoursLeft: number;
}

export const KEEP_KEYS = ["me", "0", "1", "2", "3"] as const;
const KEY = "spc-chat-v1";

const fresh = (): ChatState => ({ status: "open", minimized: false, msgs: [], keep: {}, hoursLeft: 23 });
const idle: ChatState = { status: "none", minimized: false, msgs: [], keep: {}, hoursLeft: 0 };

function load(): ChatState {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (v && (v.status === "kept" || v.status === "expired")) return { ...idle, ...v, minimized: false };
  } catch {
    /* storage unavailable */
  }
  return idle;
}

let state: ChatState = load();
const listeners = new Set<() => void>();

function set(next: ChatState) {
  state = next;
  try {
    // Only the outcome persists: a kept room moves to Messenger; an open one is per-session.
    if (next.status === "kept" || next.status === "expired") localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable */
  }
  listeners.forEach((l) => l());
}

const allKept = (keep: Record<string, boolean>) => KEEP_KEYS.every((k) => keep[k]);

export const chat = {
  get: () => state,
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  /** Called when the room opens on Sunday. No-op if a room already exists. */
  start() {
    if (state.status === "none") set(fresh());
  },
  send(text: string) {
    if (state.status !== "open") return;
    set({ ...state, msgs: [...state.msgs, { mine: true, text }] });
  },
  receive(msg: ChatMsg) {
    if (state.status !== "open") return;
    set({ ...state, msgs: [...state.msgs, msg] });
  },
  vote(key: string, on = true) {
    if (state.status !== "open") return;
    const keep = { ...state.keep, [key]: on };
    set({ ...state, keep, status: allKept(keep) ? "kept" : "open" });
  },
  minimize(minimized: boolean) {
    set({ ...state, minimized });
  },
  /** Demo timing: run the 24 h clock out. Kept rooms survive; others disappear. */
  expireNow() {
    if (state.status !== "open") return;
    set(allKept(state.keep) ? { ...state, status: "kept" } : { ...state, status: "expired", msgs: [], minimized: false });
  },
  reset() {
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* storage unavailable */
    }
    set(idle);
  },
};

export function useChat(): ChatState {
  return useSyncExternalStore(chat.subscribe, chat.get, chat.get);
}
