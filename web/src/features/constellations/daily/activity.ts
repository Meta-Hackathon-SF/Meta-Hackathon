/*
 * D010 collector for the mock Facebook shell: what "use my activity" sends.
 * Demo data only (the shell's fake Groups, friends, saved feed and the events
 * you marked Interested). Only the player's OWN posts and comments are read.
 */
import { currentUser, initialPosts, people } from "../../../data/demo";
import type { Post } from "../../../types/feed";
import type { ActivityInput } from "../privacy";

const FEED_KEY = "closer-together-feed-v1"; // the shell's demo feed (AppProvider)
const INTERESTED_KEY = "cst-interested-events";

/** Groups shown in "Your shortcuts" in the left sidebar. */
export const DEMO_GROUPS = ["g-hackathon-builders", "g-xr-student-collective"];

const slug = (name: string) => "fb-" + name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

export function readInterested(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(INTERESTED_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function writeInterested(ids: string[]) {
  try {
    localStorage.setItem(INTERESTED_KEY, JSON.stringify([...new Set(ids)].sort()));
  } catch {
    /* storage blocked: interest is just not remembered */
  }
}

function feed(): Post[] {
  try {
    const saved = JSON.parse(localStorage.getItem(FEED_KEY) ?? "null");
    return Array.isArray(saved) ? (saved as Post[]) : initialPosts;
  } catch {
    return initialPosts;
  }
}

export function collectDemoActivity(): ActivityInput {
  const posts = feed();
  const mine = posts.filter((p) => p.author?.name === currentUser.name).map((p) => p.text);
  // Comments in the demo feed are written by the current user.
  const comments = posts.flatMap((p) => (p.comments ?? []).map((c) => c.text));
  return {
    profileId: slug(currentUser.name),
    groupIds: DEMO_GROUPS,
    eventIds: readInterested(),
    friendIds: people.filter((p) => p.name !== currentUser.name).map((p) => slug(p.name)),
    texts: [...mine, ...comments].filter((t) => typeof t === "string" && t.trim()).slice(0, 50).map((t) => t.slice(0, 2000)),
  };
}
