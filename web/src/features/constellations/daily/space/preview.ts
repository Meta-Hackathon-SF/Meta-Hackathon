/* Real, non-synthetic constants for Space screens. */

/** Client-side mirror of the chat contact-info guard. The server's M1 is authoritative. */
export const CONTACT_PATTERN = /(\d[\s.()-]?){7,}|@|https?:|www\.|\.(com|net|org|edu)\b/i;

export const SUPPORT_RESOURCES = [
  { name: "988 Suicide and Crisis Lifeline", sub: "Call or text 988, any time", href: "tel:988", action: "Call" },
  { name: "Crisis Text Line", sub: "Text HOME to 741741, any time", href: "sms:741741&body=HOME", action: "Text" },
];
