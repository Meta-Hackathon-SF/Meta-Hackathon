/*
 * Per-browser demo state for the catalog: which events you registered for and
 * events you created with Muse. localStorage, wrapped in try/catch; not
 * production persistence and never shared with other viewers.
 */
import { useSyncExternalStore } from "react";
import { BASE_EVENTS, draftWhen, type CatalogEvent, type EventDraft } from "./catalog";

const KEY = "fb-demo-catalog-v1";

interface State {
  registered: string[];
  created: CatalogEvent[];
}

const IMAGES: Record<string, string> = {
  "v-cafe": "concert",
  "v-dining-north": "coffee",
  "v-library-commons": "workspace",
  "v-quad": "coast",
  "v-rec": "campus",
};

function load(): State {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (v && Array.isArray(v.registered) && Array.isArray(v.created)) {
      return {
        registered: v.registered.filter((x: unknown) => typeof x === "string"),
        created: v.created.filter((e: CatalogEvent) => e && typeof e.eventId === "string" && typeof e.title === "string"),
      };
    }
  } catch {
    /* blocked or old shape: start fresh */
  }
  return { registered: [], created: [] };
}

let state = load();
const listeners = new Set<() => void>();
const emptyState: State = { registered: [], created: [] };

function set(next: State) {
  state = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* keep in memory */
  }
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useCatalogState(): State {
  return useSyncExternalStore(subscribe, () => state, () => emptyState);
}

export function allEvents(s: State = state): CatalogEvent[] {
  return [...s.created, ...BASE_EVENTS];
}

export function findEvent(eventId: string, s: State = state): CatalogEvent | null {
  return allEvents(s).find((e) => e.eventId === eventId) ?? null;
}

export function isRegistered(eventId: string, s: State = state): boolean {
  return s.registered.includes(eventId);
}

/** Going count including you. */
export function goingCount(event: CatalogEvent, s: State = state): number {
  return event.going + (isRegistered(event.eventId, s) ? 1 : 0);
}

export function toggleRegistration(eventId: string) {
  const on = state.registered.includes(eventId);
  set({ ...state, registered: on ? state.registered.filter((x) => x !== eventId) : [...state.registered, eventId] });
}

let seq = 0;
/** Publishes a checked draft as a demo event. The creator is registered automatically. */
export function createEvent(draft: EventDraft, createdBy: string): CatalogEvent {
  const event: CatalogEvent = {
    eventId: `ev-mine-${Date.now()}-${++seq}`,
    title: draft.title,
    placeId: draft.placeId,
    start: "",
    when: draftWhen(draft),
    image: IMAGES[draft.placeId] ?? "team",
    host: createdBy,
    going: 0,
    capacity: 20,
    tags: [],
    description: draft.description || "Planned in Messenger with Muse.",
    createdBy,
  };
  set({ registered: [...state.registered, event.eventId], created: [event, ...state.created] });
  return event;
}
