import type { OnboardingCommunity } from "../onboarding/types";

/**
 * SIMULATED Facebook community context. These map the mock shell's Groups
 * cards to Group Quests community IDs. They are display fixtures, not a
 * membership source: authorization comes from Patrik's session/consent API.
 * Replace with GET-based community data once the server provides it.
 */
export const FIXTURE_COMMUNITIES: OnboardingCommunity[] = [
  {
    communityId: "hackathon-builders",
    name: "Hackathon Builders Community",
    currency: "USD",
    areas: [
      { areaId: "main-quad", name: "Main Quad" },
      { areaId: "engineering-plaza", name: "Engineering Plaza" },
      { areaId: "downtown-library", name: "Downtown Library" },
    ],
  },
  {
    communityId: "meta-ai-explorers",
    name: "Meta AI Explorers",
    currency: "USD",
    areas: [
      { areaId: "main-quad", name: "Main Quad" },
      { areaId: "student-union", name: "Student Union" },
    ],
  },
  {
    communityId: "xr-student-collective",
    name: "XR Student Collective",
    currency: "USD",
    areas: [
      { areaId: "media-lab", name: "Media Lab Commons" },
      { areaId: "student-union", name: "Student Union" },
    ],
  },
];

export const findCommunity = (communityId: string | undefined) =>
  FIXTURE_COMMUNITIES.find((c) => c.communityId === communityId) ?? null;

/** Path helper used by the mock shell's entry links. */
export const questsPath = (communityId: string) =>
  `/groups/${encodeURIComponent(communityId)}/quests`;
