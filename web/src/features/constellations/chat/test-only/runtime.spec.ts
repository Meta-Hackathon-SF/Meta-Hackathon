import { test, expect } from "@playwright/test";
import {
  parseMessage,
  parseEvidence,
  parseRoom,
  parseReveal,
  utc,
} from "../runtime";
import { parseSky } from "../../sky/runtime";

test("runtime guards reject private fields, coerced flags and unsafe aggregates", () => {
  const message = {
    messageId: "synthetic-message",
    roomId: "synthetic-room",
    handle: "Star 1",
    text: "Synthetic hello",
    createdAt: "2026-11-15T18:00:00Z",
    moderation: "visible",
    kind: "player",
  };
  expect(parseMessage(message)).toEqual(message);
  for (const change of [
    { playerId: "private-id" },
    { answer: "private-answer" },
    { text: "x".repeat(501) },
  ]) {
    expect(() => parseMessage({ ...message, ...change })).toThrow(
      "Invalid response",
    );
  }
  expect(() => utc("2026-02-30T18:00:00Z")).toThrow("Invalid response");
  expect(() =>
    parseEvidence({
      callType: "M8",
      model: "synthetic",
      source: "live",
      generatedAt: "2026-11-15T18:00:00Z",
      latencyMs: NaN,
    }),
  ).toThrow();
  expect(() =>
    parseRoom({ roomId: "synthetic", playerId: "private" }),
  ).toThrow();
  expect(() =>
    parseReveal({
      roomId: "synthetic",
      players: [],
      revealedAt: "2026-11-15T18:00:00Z",
    }),
  ).toThrow();
  const sky = {
    cycleId: "synthetic-cycle",
    threshold: 3,
    eligiblePlayers: 3,
    constellations: 1,
    mutualReveals: 0,
    themes: [],
    suppressedThemes: 0,
    headlines: [],
    syntheticSignals: [],
    evidence: [],
  };
  expect(parseSky(sky)).toEqual(sky);
  expect(() => parseSky({ ...sky, threshold: 2 })).toThrow();
  expect(() => parseSky({ ...sky, threshold: "3" })).toThrow();
  expect(() => parseSky({ ...sky, memberIds: ["private"] })).toThrow();
  expect(() =>
    parseSky({
      ...sky,
      syntheticSignals: [
        {
          signalId: "synthetic-signal",
          label: "Synthetic signal",
          percent: 25,
          sampleSize: 10,
          source: "real",
        },
      ],
    }),
  ).toThrow();
});
