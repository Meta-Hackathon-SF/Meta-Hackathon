/*
 * Facebook Space (code name: constellations) is a Facebook-wide feature,
 * not one Group's. Players see "Facebook Space"; each person's matched group is
 * still called a constellation. The server contract (2.0.0) still scopes a
 * weekly cycle and a session to one communityId, so the UI plays in this
 * default community until D009/D010 are decided (see docs/handoffs/will.md).
 */
export const FEATURE_NAME = "Facebook Space";
export const PLAY_COMMUNITY = "hackathon-builders";
export const JOIN_SCOPE_LABEL = "your groups";
export const CONSTELLATIONS_PATH = "/space";
export const OPERATOR_PATH = "/space/operator";
