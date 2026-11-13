/*
 * D010 topic allowlist, a copy of SAFE_TOPICS in server/privacy/activity.py.
 * Used only by the FIXTURE client so the demo behaves like the server: text
 * becomes allowlisted labels and is discarded. No sensitive categories exist
 * here, so they can never become a matching signal.
 */
export const SAFE_TOPICS: Record<string, string[]> = {
  ai: ["ai", "llama", "llm", "machine learning", "model", "models"],
  coding: ["code", "coding", "hackathon", "prototype", "programming", "cs"],
  design: ["design", "designer", "figma", "ui", "ux"],
  music: ["music", "song", "songs", "concert", "band", "playlist", "singing"],
  gaming: ["game", "games", "gaming", "board game", "board games"],
  vr: ["vr", "ar", "xr", "headset", "virtual reality"],
  study: ["study", "studying", "library", "exam", "exams", "class"],
  coffee: ["coffee", "cafe", "café", "espresso"],
  food: ["cooking", "dinner", "lunch", "breakfast", "recipe", "dining hall"],
  outdoors: ["hike", "hiking", "outdoors", "walk", "walking", "park", "trail"],
  sports: ["volleyball", "basketball", "soccer", "gym", "running", "climbing"],
  film: ["movie", "movies", "film", "films"],
  art: ["art", "drawing", "painting", "photography", "photo"],
  books: ["book", "books", "reading", "novel"],
};

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const PATTERNS = Object.entries(SAFE_TOPICS).map(
  ([label, words]) => [label, new RegExp(`(^|[^\\p{L}\\p{N}_])(${words.map(escape).join("|")})(?=$|[^\\p{L}\\p{N}_])`, "u")] as const,
);

export function deriveTopics(texts: string[]): string[] {
  const found = new Set<string>();
  for (const text of texts) {
    const lowered = text.toLowerCase();
    for (const [label, pattern] of PATTERNS) if (pattern.test(lowered)) found.add(label);
  }
  return [...found].sort();
}
