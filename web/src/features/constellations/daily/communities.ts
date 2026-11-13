/*
 * Constellations is a Facebook-wide feature, not one Group's.
 * The server contract (2.0.0) still scopes a weekly cycle and a session to one
 * communityId, so the UI plays in this default community until the team
 * decides how shared Groups should brighten a match (see docs/handoffs/will.md).
 */
export const PLAY_COMMUNITY = "hackathon-builders";
export const JOIN_SCOPE_LABEL = "your groups";
export const CONSTELLATIONS_PATH = "/constellations";
export const OPERATOR_PATH = "/constellations/operator";
