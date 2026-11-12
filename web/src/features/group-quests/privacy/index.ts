/**
 * Group Quests privacy UI (owner: Patrik). Will composes these in the feature shell.
 *
 *   <PrivacyCenter client={httpPrivacyClient()} communityId="demo-campus"
 *     communityName="Demo Campus" onMatchableChange={setMatchable} />
 *
 * Use fixturePrivacyClient() only for local UI work; it renders a "Fixture mode" badge.
 */
export { httpPrivacyClient, fixturePrivacyClient, PrivacyApiError } from "./client";
export type { ConsentToggles, MembershipView, PrivacyClient, SessionView } from "./client";
export { ConsentPanel, ConsentToggleList, MatchableStatus } from "./ConsentControls";
export { CONSENT_COPY, formatMoney, isMatchable } from "./consent";
export type { ConsentPanelProps } from "./ConsentControls";
export { PrivacyCenter, JoinCommunityCard, PublicPreview, LeaveCommunity, FixtureBadge } from "./PrivacyCenter";
export type { PrivacyCenterProps, JoinCommunityCardProps, PublicPreviewProps, LeaveCommunityProps } from "./PrivacyCenter";
export { PrivacySlot } from "./PrivacySlot";
export type { PrivacySlotProps } from "./PrivacySlot";
export { usePrivacySession } from "./usePrivacySession";
export type { SessionState } from "./usePrivacySession";
