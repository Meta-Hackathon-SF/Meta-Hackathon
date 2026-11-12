import { useMemo } from "react";
import type { Consent, Id, Mode } from "../../../../../contracts/protocol";
import { fixturePrivacyClient, httpPrivacyClient } from "./client";
import { PrivacyCenter } from "./PrivacyCenter";

/**
 * Adapter for Will's feature shell privacy slot (shell/slots.ts PrivacySlotProps):
 * `{ communityId, mode, onConsentChange }`. Fixture mode uses the in-memory client
 * (visible badge); live and replay use the server session API.
 */
export interface PrivacySlotProps {
  communityId: Id;
  mode: Mode;
  onConsentChange: (consent: Consent | null) => void;
  communityName?: string;
  apiBase?: string;
}

export function PrivacySlot({ communityId, mode, onConsentChange, communityName, apiBase }: PrivacySlotProps) {
  const client = useMemo(
    () => (mode === "fixture" ? fixturePrivacyClient() : httpPrivacyClient(apiBase)),
    [mode, apiBase],
  );
  return (
    <PrivacyCenter
      client={client}
      communityId={communityId}
      communityName={communityName ?? "this community"}
      onConsentChange={onConsentChange}
    />
  );
}

export default PrivacySlot;
