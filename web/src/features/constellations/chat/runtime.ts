import type {
  ChatMessage,
  ChatRoom,
  MutualReveal,
  MuseCallEvidence,
} from "../../../../../contracts/protocol";

export function object(
  value: unknown,
  keys: readonly string[],
): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid response");
  const row = value as Record<string, unknown>;
  if (
    Object.keys(row).length !== keys.length ||
    keys.some((key) => !(key in row))
  )
    throw new Error("Invalid response");
  return row;
}
export function text(value: unknown): asserts value is string {
  if (typeof value !== "string" || !value.trim())
    throw new Error("Invalid response");
}
export function number(
  value: unknown,
  min = 0,
  max = Infinity,
): asserts value is number {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < min ||
    value > max
  )
    throw new Error("Invalid response");
}
export function integer(value: unknown, min = 0): asserts value is number {
  number(value, min);
  if (!Number.isInteger(value)) throw new Error("Invalid response");
}
export function boolean(value: unknown): asserts value is boolean {
  if (typeof value !== "boolean") throw new Error("Invalid response");
}
export function utc(value: unknown): asserts value is string {
  text(value);
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/.test(
      value,
    ) ||
    !Number.isFinite(Date.parse(value))
  )
    throw new Error("Invalid response");
  if (new Date(value).toISOString().slice(0, 19) !== value.slice(0, 19))
    throw new Error("Invalid response");
}
export function list(value: unknown): asserts value is unknown[] {
  if (!Array.isArray(value)) throw new Error("Invalid response");
}
export function oneOf(value: unknown, values: readonly unknown[]) {
  if (!values.includes(value)) throw new Error("Invalid response");
}
export function parseMessage(value: unknown): ChatMessage {
  const row = object(value, [
    "messageId",
    "roomId",
    "handle",
    "text",
    "createdAt",
    "moderation",
    "kind",
  ]);
  for (const key of ["messageId", "roomId", "handle", "text"]) text(row[key]);
  if ((row.text as string).length > 500) throw new Error("Invalid response");
  utc(row.createdAt);
  oneOf(row.moderation, ["visible", "hidden_pending", "removed"]);
  oneOf(row.kind, ["player", "system", "muse_nudge"]);
  return row as unknown as ChatMessage;
}
export function parseRoom(value: unknown): ChatRoom {
  const row = object(value, [
    "roomId",
    "constellationId",
    "cycleId",
    "status",
    "opensAt",
    "expiresAt",
    "members",
  ]);
  for (const key of ["roomId", "constellationId", "cycleId"]) text(row[key]);
  oneOf(row.status, ["open", "expired", "closed"]);
  utc(row.opensAt);
  utc(row.expiresAt);
  list(row.members);
  if (Date.parse(row.opensAt) >= Date.parse(row.expiresAt))
    throw new Error("Invalid response");
  const handles = new Set<string>();
  let selves = 0;
  for (const value of row.members) {
    const m = object(value, ["roomId", "handle", "starColor", "isSelf"]);
    text(m.handle);
    text(m.starColor);
    boolean(m.isSelf);
    if (m.roomId !== row.roomId || handles.has(m.handle))
      throw new Error("Invalid response");
    handles.add(m.handle);
    if (m.isSelf) selves += 1;
  }
  if (selves > 1) throw new Error("Invalid response");
  return row as unknown as ChatRoom;
}
export function parseReveal(value: unknown): MutualReveal {
  const row = object(value, ["roomId", "players", "revealedAt"]);
  text(row.roomId);
  utc(row.revealedAt);
  list(row.players);
  if (row.players.length !== 2) throw new Error("Invalid response");
  const ids = new Set<string>();
  for (const value of row.players) {
    const p = object(value, [
      "playerId",
      "displayName",
      "avatarColor",
      "isSynthetic",
    ]);
    text(p.playerId);
    text(p.displayName);
    text(p.avatarColor);
    boolean(p.isSynthetic);
    ids.add(p.playerId);
  }
  if (ids.size !== 2) throw new Error("Invalid response");
  return row as unknown as MutualReveal;
}
export function parseEvidence(value: unknown): MuseCallEvidence {
  const row = object(value, [
    "callType",
    "model",
    "source",
    "generatedAt",
    "latencyMs",
  ]);
  oneOf(row.callType, ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"]);
  oneOf(row.source, ["live", "replay"]);
  text(row.model);
  utc(row.generatedAt);
  number(row.latencyMs);
  return row as unknown as MuseCallEvidence;
}
