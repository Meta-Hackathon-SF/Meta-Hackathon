/**
 * Demo Messenger inbox for the Facebook shell. Session-only, separate from the
 * feed's localStorage. A Sunday constellation lands here once every member
 * agrees to keep the temporary chat.
 */
import { useSyncExternalStore } from "react";
import type { EventDraft } from "../../catalog/catalog";

const STORAGE_KEY = "fb-space-messenger-demo";

export const SUNDAY_THREAD_ID = "sunday-constellation";
export const JORDAN_THREAD_ID = "jordan-davis";

export interface InboxMessage {
  id: string;
  senderName: string;
  text: string;
  mine: boolean;
  fromMuse?: boolean;
  /** "live" is a Muse reply. "catalog" is the allowlisted fallback when Muse does not answer. */
  source?: "live" | "catalog";
  /** Catalog ids Muse pointed at; rendered as Marketplace / Event cards. */
  itemIds?: string[];
  eventIds?: string[];
  /** A Muse event draft, and the event id once someone tapped Create. */
  draft?: EventDraft;
  createdEventId?: string;
  /** When it was added here (local Muse lines are merged with live room messages by time). */
  at?: string;
}

export interface InboxThread {
  id: string;
  kind: "direct" | "group";
  title: string;
  memberNames: string[];
  messages: InboxMessage[];
  preview: string;
  /** Set on a thread opened with a server-seeded synthetic player. */
  synthetic?: boolean;
  /** Hosted app: this thread is a view of the real Sunday room (messages sync across accounts). */
  live?: { cycleId: string; roomId: string };
}

export interface SundayLine {
  senderName: string;
  text: string;
  mine: boolean;
}

function direct(id: string, name: string, text: string): InboxThread {
  return {
    id,
    kind: "direct",
    title: name,
    memberNames: [name],
    messages: [{ id: `${id}-0`, senderName: name, text, mine: false }],
    preview: text,
  };
}

function seed(): InboxThread[] {
  return [
    direct("maya-chen", "Maya Chen", "See you at the hackathon!"),
    direct(JORDAN_THREAD_ID, "Jordan Davis", "How is the build going?"),
    direct("sofia-patel", "Sofia Patel", "Sent you a photo"),
    direct("daniel-kim", "Daniel Kim", "Want to grab a table later?"),
  ];
}

function validThread(value: unknown): value is InboxThread {
  if (!value || typeof value !== "object") return false;
  const thread = value as InboxThread;
  return (
    typeof thread.id === "string" &&
    (thread.kind === "direct" || thread.kind === "group") &&
    typeof thread.title === "string" &&
    Array.isArray(thread.memberNames) &&
    thread.memberNames.every((name) => typeof name === "string") &&
    Array.isArray(thread.messages) &&
    thread.messages.every(
      (message) =>
        typeof message?.id === "string" &&
        typeof message.senderName === "string" &&
        typeof message.text === "string" &&
        typeof message.mine === "boolean",
    ) &&
    typeof thread.preview === "string"
  );
}

function load(): InboxThread[] {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if (Array.isArray(saved) && saved.length && saved.every(validThread)) return saved;
  } catch {
    /* A private window or an older demo shape falls back to the seed. */
  }
  return seed();
}

let threads = load();
const serverThreads = seed();
const listeners = new Set<() => void>();

function emit() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
  } catch {
    /* Keep the in-memory inbox if storage is blocked. */
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useInbox(): InboxThread[] {
  return useSyncExternalStore(subscribe, () => threads, () => serverThreads);
}

export function isSundayPromoted(): boolean {
  return threads.some((thread) => thread.id === SUNDAY_THREAD_ID);
}

let seq = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${++seq}`;

export function promoteSundayChat(lines: SundayLine[], memberNames: string[]) {
  if (isSundayPromoted() || lines.length === 0) return;
  const messages = lines.map((line, index) => ({
    id: `sun-${index}`,
    senderName: line.senderName,
    text: line.text,
    mine: line.mine,
  }));
  const thread: InboxThread = {
    id: SUNDAY_THREAD_ID,
    kind: "group",
    title: "Sunday constellation",
    memberNames,
    messages,
    preview: messages[messages.length - 1]?.text ?? "Names are visible",
  };
  threads = [thread, ...threads];
  emit();
}

/** Opens (or creates) a direct thread with a player after a real mutual reveal. Returns the thread id. */
/** Hosted app: puts the real Sunday room in Messenger (or refreshes the link to it). */
export function promoteLiveRoom(cycleId: string, roomId: string) {
  const existing = threads.find((t) => t.id === SUNDAY_THREAD_ID);
  if (existing?.live?.roomId === roomId) return;
  const thread: InboxThread = {
    id: SUNDAY_THREAD_ID,
    kind: "group",
    title: "Sunday constellation",
    memberNames: [],
    messages: [],
    preview: "Your constellation's chat",
    live: { cycleId, roomId },
  };
  threads = [thread, ...threads.filter((t) => t.id !== SUNDAY_THREAD_ID)];
  emit();
}

export function openRevealThread(playerId: string, displayName: string, synthetic = false): string {
  const id = `reveal-${playerId}`;
  if (!threads.some((thread) => thread.id === id)) {
    threads = [{ id, kind: "direct", title: displayName, memberNames: [displayName], messages: [], preview: "", synthetic }, ...threads];
    emit();
  }
  return id;
}

export function addMuseMessage(
  threadId: string,
  help: { text: string; source: "live" | "catalog"; itemIds: string[]; eventIds: string[]; draft: EventDraft | null },
) {
  const message: InboxMessage = {
    id: nextId("muse"),
    senderName: "Muse",
    text: help.text,
    mine: false,
    fromMuse: true,
    at: new Date().toISOString(),
    source: help.source,
    itemIds: help.itemIds,
    eventIds: help.eventIds,
    draft: help.draft ?? undefined,
  };
  threads = threads.map((thread) =>
    thread.id === threadId
      ? { ...thread, messages: [...thread.messages, message], preview: help.text }
      : thread,
  );
  emit();
}

/** Records that a draft was turned into an event, and shares the event card in the thread. */
export function markDraftCreated(threadId: string, messageId: string, eventId: string, title: string) {
  threads = threads.map((thread) =>
    thread.id === threadId
      ? {
          ...thread,
          messages: [
            ...thread.messages.map((m) => (m.id === messageId ? { ...m, createdEventId: eventId } : m)),
            { id: nextId("out"), senderName: "Alex Morgan", text: `Created ${title}. Register here:`, mine: true, eventIds: [eventId], at: new Date().toISOString() },
          ],
          preview: `Created ${title}`,
        }
      : thread,
  );
  emit();
}

export function sendInboxMessage(threadId: string, text: string) {
  const trimmed = text.trim();
  if (!trimmed) return;
  const message: InboxMessage = {
    id: nextId("out"),
    senderName: "Alex Morgan",
    text: trimmed,
    mine: true,
  };
  threads = threads.map((thread) =>
    thread.id === threadId
      ? { ...thread, messages: [...thread.messages, message], preview: trimmed }
      : thread,
  );
  emit();
}
