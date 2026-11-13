export {
  allOn,
  fixturePrivacyClient,
  getPrivacyClient,
  httpPrivacyClient,
  parseConsent,
  parseSession,
  ACTIVITY_EVENT,
  PrivacyError,
  readFixtureActivity,
} from "./client";
export type { ActivityInput, ActivityResult, ConsentToggles, FixtureActivity, PrivacyClient, SessionView } from "./client";
export { FixtureBadge, JoinScreen, PrivacyGate, PrivacySettings, SupportCard } from "./PrivacyComponents";
export { usePrivacySession } from "./usePrivacySession";
export type { PrivacyState } from "./usePrivacySession";
