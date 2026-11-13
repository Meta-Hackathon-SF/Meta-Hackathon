/*
 * Facebook Space (code name: constellations) is Facebook-wide, not one
 * Group's. Everyone plays in one pool, "facebook-space" (seeded by
 * db/privacy/004_activity.sql). Groups are a matching signal (D010): people in
 * the same Groups shine a little brighter, they are not a boundary.
 * Players see "Facebook Space"; each person's matched group is a "constellation".
 */
export const FEATURE_NAME = "Facebook Space";
export const PLAY_COMMUNITY = "facebook-space";
export const JOIN_SCOPE_LABEL = "all of Facebook";
export const CONSTELLATIONS_PATH = "/space";
export const OPERATOR_PATH = "/space/operator";
