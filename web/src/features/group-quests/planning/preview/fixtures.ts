// SYNTHETIC fixture data for the dev-only planning preview. Mirrors the shape
// produced by server/planning in fixture mode (tests/planning/fixtures.py).
import type { Continuation, PublicPlanCard } from "../types";

const fixtureEvidence = {
  model: "fixture:scripted-muse",
  source: "replay" as const,
  generatedAt: "2026-11-12T20:00:00.000Z",
  latencyMs: 5,
};

export const planRev1: PublicPlanCard = {
  planId: "plan-fixture-1",
  revision: 1,
  basedOnRevision: null,
  title: "Three-Photo Story Walk",
  activity: "Take a slow loop around the quad and each spot one scene that could open, middle or end a story.",
  collaborationTask: "Together pick three photos, put them in order and agree on a one-line caption for the story.",
  venue: { venueId: "venue-demo-quad", name: "Main Quad (synthetic demo venue)", publicAddress: "Demo address withheld: Main Quad" },
  start: "2026-11-14T22:30:00Z",
  end: "2026-11-14T23:30:00Z",
  timeZone: "America/Los_Angeles",
  costPerPersonMinor: 0,
  currency: "USD",
  publicRationale:
    "This quest builds on the group's shared interest in photography, fits a time that works for everyone, is free, takes about an hour or less, and happens at an approved public venue. The group makes something together rather than doing it side by side.",
  evidence: fixtureEvidence,
};

export const planRev2: PublicPlanCard = {
  ...planRev1,
  planId: "plan-fixture-2",
  revision: 2,
  basedOnRevision: 1,
  start: "2026-11-14T23:00:00Z",
  end: "2026-11-14T23:45:00Z",
};

export const continuation: Continuation = {
  questId: "quest-fixture-1",
  proposedHostId: "p-cy",
  nextActivity: "A golden-hour photo walk where the group builds a five-photo story with a twist ending.",
  invitationText: "Want to do a part two next week? Let's make a five-photo story at golden hour. Reply if you're in!",
  evidence: fixtureEvidence,
};

export const liveEvidenceExample = { ...fixtureEvidence, model: "muse-spark-1.3", source: "live" as const, latencyMs: 2400 };
