/**
 * Demo Messenger inbox for the Facebook shell. Session-only, separate from the
 * feed's localStorage. A Sunday constellation lands here once every member
 * agrees to keep the temporary chat.
 */
import { useSyncExternalStore } from "react";

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
  linkHref?: string;
  linkLabel?: string;
}

export interface InboxThread {
  id: string;
  kind: "direct" | "group";
  title: string;
  memberNames: string[];
  messages: InboxMessage[];
  preview: string;
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

export function addMuseMessage(
  threadId: string,
  text: string,
  source: "live" | "catalog",
  link?: { href: string; label: string },
) {
  const message: InboxMessage = {
    id: nextId("muse"),
    senderName: "Muse",
    text,
    mine: false,
    fromMuse: true,
    source,
    linkHref: link?.href,
    linkLabel: link?.label,
  };
  threads = threads.map((thread) =>
    thread.id === threadId
      ? { ...thread, messages: [...thread.messages, message], preview: text }
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
