import type { ConsentToggles } from "./client";

export const TOGGLES: { key: keyof ConsentToggles; label: string; detail: string }[] = [
  {
    key: "matchAnswers",
    label: "Match me by my answers",
    detail: "Muse reads your answers privately to place you with 3 to 5 people this week. Nobody sees your answers.",
  },
  {
    key: "anonymousChat",
    label: "Join my constellation's anonymous chat",
    detail: "On Sunday you join a moderated chat as a Star handle, not your name. It closes at the next Saturday lock.",
  },
  {
    key: "isAdult",
    label: "I'm 18 or older",
    detail: "Facebook Space is for adults only, and for friendship only.",
  },
];

export const PRIVATE_ITEMS = [
  "Your daily answers and how you answered",
  "Your streak and catch-up days",
  "Anything flagged by the safety check",
];

export const SHARED_ITEMS = [
  "Your constellation's name, with the people in it",
  "A Star handle in your constellation's chat",
  "Group-wide patterns in the Sky, only when 3 or more people share them",
  "Your name, only if you and another player both choose to reveal",
];

export const NO_TOGGLES: ConsentToggles = { matchAnswers: false, anonymousChat: false, isAdult: false };
