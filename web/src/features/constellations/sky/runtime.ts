import type { SkyStats } from "../../../../../contracts/protocol";
import {
  integer,
  list,
  number,
  object,
  parseEvidence,
  text,
} from "../chat/runtime";

export function parseSky(value: unknown): SkyStats {
  const row = object(value, [
    "cycleId",
    "threshold",
    "eligiblePlayers",
    "constellations",
    "mutualReveals",
    "themes",
    "suppressedThemes",
    "headlines",
    "syntheticSignals",
    "evidence",
  ]);
  text(row.cycleId);
  integer(row.threshold, 3);
  for (const key of [
    "eligiblePlayers",
    "constellations",
    "mutualReveals",
    "suppressedThemes",
  ])
    integer(row[key]);
  list(row.themes);
  list(row.headlines);
  list(row.syntheticSignals);
  list(row.evidence);
  const ids = new Set<string>();
  for (const value of row.themes) {
    const t = object(value, [
      "themeId",
      "label",
      "count",
      "actualPercent",
      "guessedPercentMedian",
    ]);
    text(t.themeId);
    text(t.label);
    integer(t.count);
    number(t.actualPercent, 0, 100);
    number(t.guessedPercentMedian, 0, 100);
    if (t.count > (row.eligiblePlayers as number) || ids.has(t.themeId))
      throw new Error("Invalid response");
    ids.add(t.themeId);
  }
  row.headlines.forEach(text);
  for (const value of row.syntheticSignals) {
    const s = object(value, [
      "signalId",
      "label",
      "percent",
      "sampleSize",
      "source",
    ]);
    text(s.signalId);
    text(s.label);
    number(s.percent, 0, 100);
    integer(s.sampleSize, 1);
    if (s.source !== "synthetic") throw new Error("Invalid response");
  }
  row.evidence.forEach(parseEvidence);
  return row as unknown as SkyStats;
}
