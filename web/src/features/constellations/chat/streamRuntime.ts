import type {
  StreamEvent,
  WeeklyCycle,
} from "../../../../../contracts/protocol";
import {
  boolean,
  integer,
  object,
  oneOf,
  parseMessage,
  parseReveal,
  text,
  utc,
} from "./runtime";

function sequence(value: unknown): asserts value is number {
  integer(value, 1);
  if (!Number.isSafeInteger(value)) throw new Error("Invalid response");
}

export function parseWeeklyCycle(value: unknown): WeeklyCycle {
  const row = object(value, [
    "cycleId",
    "communityId",
    "weekStart",
    "status",
    "currentDay",
    "locksAt",
    "revealsAt",
    "chatExpiresAt",
    "demoTiming",
  ]);
  text(row.cycleId);
  text(row.communityId);
  text(row.weekStart);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(row.weekStart))
    throw new Error("Invalid response");
  utc(`${row.weekStart}T00:00:00Z`);
  if (new Date(`${row.weekStart}T00:00:00Z`).getUTCDay() !== 1)
    throw new Error("Invalid response");
  oneOf(row.status, ["open", "locked", "forming", "revealed", "closed"]);
  integer(row.currentDay, 1);
  oneOf(row.currentDay, [1, 2, 3, 4, 5]);
  utc(row.locksAt);
  utc(row.revealsAt);
  utc(row.chatExpiresAt);
  boolean(row.demoTiming);
  if (
    !(
      Date.parse(row.locksAt) < Date.parse(row.revealsAt) &&
      Date.parse(row.revealsAt) < Date.parse(row.chatExpiresAt)
    )
  )
    throw new Error("Invalid response");
  return row as unknown as WeeklyCycle;
}

export function parseStreamEvent(value: unknown): StreamEvent {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid response");
  const kind = (value as Record<string, unknown>).type;
  let row: Record<string, unknown>;
  switch (kind) {
    case "cycle.updated":
      row = object(value, ["type", "seq", "cycle"]);
      parseWeeklyCycle(row.cycle);
      break;
    case "constellation.revealed":
    case "room.expired":
      row = object(value, ["type", "seq", "roomId"]);
      text(row.roomId);
      break;
    case "chat.message":
      row = object(value, ["type", "seq", "message"]);
      parseMessage(row.message);
      break;
    case "chat.moderated":
      row = object(value, ["type", "seq", "messageId", "moderation"]);
      text(row.messageId);
      oneOf(row.moderation, ["visible", "hidden_pending", "removed"]);
      break;
    case "reveal.mutual":
      row = object(value, ["type", "seq", "reveal"]);
      parseReveal(row.reveal);
      break;
    case "sky.updated":
      row = object(value, ["type", "seq", "cycleId"]);
      text(row.cycleId);
      break;
    default:
      throw new Error("Invalid response");
  }
  sequence(row.seq);
  return row as unknown as StreamEvent;
}
