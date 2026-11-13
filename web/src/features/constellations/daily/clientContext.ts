import { apiBase } from "../apiBase";
/*
 * Chooses the client once per page load. Live mode needs VITE_CONSTELLATIONS_API
 * (for example "/api/v1"); without it the labeled fixture adapter is used.
 */
import type { CycleClient } from "./client";
import { createFixtureClient } from "./fixtureClient";
import { createHttpClient } from "./httpClient";

let client: CycleClient | null = null;

export function getCycleClient(communityId: string): CycleClient {
  if (!client) {
    const base = apiBase();
    // In live mode the server decides who is an operator; the console just tries.
    client = base ? createHttpClient(base, { isOperator: false, communityId }) : createFixtureClient();
  }
  return client;
}
