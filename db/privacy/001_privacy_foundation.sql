-- Group Quests privacy foundation (owner: Patrik). Contract v1.0.0.
--
-- Access model
--   * The API connects as a LOGIN role that is a member of gq_api (never the
--     table owner, never a superuser, never a Supabase service role).
--   * Per transaction the server sets gq.participant_id ONLY from a verified
--     session (server/privacy/db.py). Unset => privacy.actor() is NULL and every
--     policy below evaluates false: fail closed.
--   * Direct table access is self-only. Cross-participant reads happen only
--     through the SECURITY DEFINER functions at the bottom, which re-check
--     membership and consent and return minimized rows.
--   * Session tokens are stored as SHA-256 hashes; gq_api cannot read sessions.
--
-- Retention: one current private_intents row per participant/community
-- (overwritten on update, deleted on leave). Consent revisions are kept as an
-- audit trail; they contain booleans and timestamps only.
--
-- Migration order: this file runs before db/workflow/ (Kai), whose tables may
-- reference privacy.participants(participant_id) and privacy.communities.

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gq_api') THEN
    CREATE ROLE gq_api NOLOGIN;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS privacy;
REVOKE ALL ON SCHEMA privacy FROM PUBLIC;
GRANT USAGE ON SCHEMA privacy TO gq_api;

CREATE OR REPLACE FUNCTION privacy.actor() RETURNS text
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('gq.participant_id', true), '') $$;

CREATE OR REPLACE FUNCTION privacy.new_id(prefix text) RETURNS text
LANGUAGE sql VOLATILE
AS $$ SELECT prefix || '_' || replace(gen_random_uuid()::text, '-', '') $$;

CREATE TABLE privacy.participants (
  participant_id text PRIMARY KEY DEFAULT privacy.new_id('p'),
  is_synthetic   boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE privacy.sessions (
  session_id     text PRIMARY KEY DEFAULT privacy.new_id('s'),
  token_hash     bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
  participant_id text NOT NULL REFERENCES privacy.participants ON DELETE CASCADE,
  created_at     timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz NOT NULL,
  revoked_at     timestamptz,
  CHECK (expires_at > created_at)
);

CREATE TABLE privacy.communities (
  community_id text PRIMARY KEY,
  name         text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
  area_ids     text[] NOT NULL CHECK (cardinality(area_ids) > 0),
  currency     text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  is_demo      boolean NOT NULL DEFAULT false
);

CREATE TABLE privacy.memberships (
  community_id   text NOT NULL REFERENCES privacy.communities,
  participant_id text NOT NULL REFERENCES privacy.participants ON DELETE CASCADE,
  display_name   text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 40),
  joined_at      timestamptz NOT NULL DEFAULT now(),
  left_at        timestamptz,
  PRIMARY KEY (community_id, participant_id)
);

CREATE TABLE privacy.consents (
  participant_id   text NOT NULL,
  community_id     text NOT NULL,
  version          integer NOT NULL CHECK (version >= 1),
  matching         boolean NOT NULL,
  model_processing boolean NOT NULL,
  public_interests boolean NOT NULL,
  revoked_at       timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (participant_id, community_id, version),
  FOREIGN KEY (community_id, participant_id)
    REFERENCES privacy.memberships (community_id, participant_id) ON DELETE CASCADE
);

CREATE TABLE privacy.private_intents (
  participant_id       text NOT NULL,
  community_id         text NOT NULL,
  intent_version       integer NOT NULL CHECK (intent_version >= 1),
  goal                 text NOT NULL CHECK (char_length(goal) BETWEEN 1 AND 500),
  interests            text[] NOT NULL CHECK (cardinality(interests) BETWEEN 1 AND 10),
  area_id              text NOT NULL,
  time_zone            text NOT NULL,
  availability         jsonb NOT NULL CHECK (jsonb_typeof(availability) = 'array'),
  max_budget_minor     bigint NOT NULL CHECK (max_budget_minor >= 0),
  currency             text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  max_duration_minutes integer NOT NULL CHECK (max_duration_minutes BETWEEN 15 AND 1440),
  consent_version      integer NOT NULL CHECK (consent_version >= 1),
  confirmed_at         timestamptz NOT NULL,
  PRIMARY KEY (participant_id, community_id),
  FOREIGN KEY (community_id, participant_id)
    REFERENCES privacy.memberships (community_id, participant_id) ON DELETE CASCADE
);

-- Row-level security: self-only for direct access.
ALTER TABLE privacy.participants    ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy.sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy.communities     ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy.memberships     ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy.consents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy.private_intents ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON privacy.participants TO gq_api;
CREATE POLICY participants_self ON privacy.participants
  FOR SELECT TO gq_api USING (participant_id = privacy.actor());

-- No grants on sessions: only the SECURITY DEFINER functions touch it.

GRANT SELECT ON privacy.communities TO gq_api;
CREATE POLICY communities_read ON privacy.communities
  FOR SELECT TO gq_api USING (privacy.actor() IS NOT NULL);

GRANT SELECT, INSERT, UPDATE ON privacy.memberships TO gq_api;
CREATE POLICY memberships_self ON privacy.memberships
  FOR ALL TO gq_api
  USING (participant_id = privacy.actor())
  WITH CHECK (participant_id = privacy.actor());

GRANT SELECT, INSERT ON privacy.consents TO gq_api;
CREATE POLICY consents_self_read ON privacy.consents
  FOR SELECT TO gq_api USING (participant_id = privacy.actor());
CREATE POLICY consents_self_insert ON privacy.consents
  FOR INSERT TO gq_api WITH CHECK (participant_id = privacy.actor());

GRANT SELECT, INSERT, UPDATE, DELETE ON privacy.private_intents TO gq_api;
CREATE POLICY intents_self ON privacy.private_intents
  FOR ALL TO gq_api
  USING (participant_id = privacy.actor())
  WITH CHECK (participant_id = privacy.actor());

-- Current consent per member (latest revision).
CREATE VIEW privacy.current_consents WITH (security_invoker = true) AS
  SELECT DISTINCT ON (participant_id, community_id) *
  FROM privacy.consents
  ORDER BY participant_id, community_id, version DESC;
GRANT SELECT ON privacy.current_consents TO gq_api;

-- ---------------------------------------------------------------------------
-- Session functions (token hashes only; raw tokens never reach the database).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION privacy.create_guest_session(p_token_hash bytea, p_ttl interval)
RETURNS TABLE (participant_id text, session_id text, expires_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, privacy
AS $$
DECLARE
  v_participant text;
BEGIN
  IF p_ttl <= interval '0' OR p_ttl > interval '30 days' THEN
    RAISE EXCEPTION 'invalid session ttl' USING ERRCODE = '22023';
  END IF;
  INSERT INTO privacy.participants (is_synthetic) VALUES (false)
    RETURNING participants.participant_id INTO v_participant;
  RETURN QUERY
    INSERT INTO privacy.sessions (token_hash, participant_id, expires_at)
    VALUES (p_token_hash, v_participant, now() + p_ttl)
    RETURNING sessions.participant_id, sessions.session_id, sessions.expires_at;
END
$$;

-- Synthetic participants can never hold a live session (fixture impersonation guard).
CREATE OR REPLACE FUNCTION privacy.resolve_session(p_token_hash bytea)
RETURNS TABLE (participant_id text, session_id text, expires_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, privacy
AS $$
  SELECT s.participant_id, s.session_id, s.expires_at
  FROM privacy.sessions s
  JOIN privacy.participants p USING (participant_id)
  WHERE s.token_hash = p_token_hash
    AND s.revoked_at IS NULL
    AND s.expires_at > now()
    AND NOT p.is_synthetic
$$;

CREATE OR REPLACE FUNCTION privacy.revoke_session(p_token_hash bytea)
RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, privacy
AS $$
  WITH r AS (
    UPDATE privacy.sessions SET revoked_at = now()
    WHERE token_hash = p_token_hash AND revoked_at IS NULL
    RETURNING 1
  )
  SELECT EXISTS (SELECT 1 FROM r)
$$;

-- ---------------------------------------------------------------------------
-- Authorized cross-participant reads.
-- ---------------------------------------------------------------------------
-- Eligible = active member + latest consent grants matching AND model
-- processing + a confirmed intent in this community.
CREATE OR REPLACE FUNCTION privacy.is_eligible(p_community text, p_participant text)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, privacy
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM privacy.memberships m
    JOIN privacy.current_consents c
      ON c.community_id = m.community_id AND c.participant_id = m.participant_id
    JOIN privacy.private_intents i
      ON i.community_id = m.community_id AND i.participant_id = m.participant_id
    WHERE m.community_id = p_community
      AND m.participant_id = p_participant
      AND m.left_at IS NULL
      AND c.matching AND c.model_processing
  )
$$;

-- Candidate snapshot for a matching job run on behalf of the current actor.
-- Raises GQ403 when the actor is not itself eligible. Returns only the fields
-- of the Candidate wire type; public interests are emptied without consent.
CREATE OR REPLACE FUNCTION privacy.authorized_candidates(p_community text)
RETURNS TABLE (
  participant_id text, display_name text, is_synthetic boolean,
  public_interests_consent boolean, consent_version integer,
  intent_version integer, goal text, interests text[], area_id text,
  time_zone text, availability jsonb, max_budget_minor bigint, currency text,
  max_duration_minutes integer, confirmed_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, privacy
AS $$
DECLARE
  v_actor text := privacy.actor();
BEGIN
  IF v_actor IS NULL THEN
    RAISE EXCEPTION 'unauthenticated' USING ERRCODE = 'GQ401';
  END IF;
  IF NOT privacy.is_eligible(p_community, v_actor) THEN
    RAISE EXCEPTION 'consent required' USING ERRCODE = 'GQ403';
  END IF;
  RETURN QUERY
    SELECT m.participant_id, m.display_name, p.is_synthetic,
           c.public_interests, c.version,
           i.intent_version, i.goal, i.interests, i.area_id, i.time_zone,
           i.availability, i.max_budget_minor, i.currency,
           i.max_duration_minutes, i.confirmed_at
    FROM privacy.memberships m
    JOIN privacy.participants p ON p.participant_id = m.participant_id
    JOIN privacy.current_consents c
      ON c.community_id = m.community_id AND c.participant_id = m.participant_id
    JOIN privacy.private_intents i
      ON i.community_id = m.community_id AND i.participant_id = m.participant_id
    WHERE m.community_id = p_community
      AND m.left_at IS NULL
      AND c.matching AND c.model_processing
    ORDER BY m.participant_id;
END
$$;

-- Version/eligibility recheck used before publishing a job result (Kai).
-- Returns versions only, never private content, and only when the actor is in
-- the requested set (a member checking their own group).
CREATE OR REPLACE FUNCTION privacy.member_versions(p_community text, p_participants text[])
RETURNS TABLE (participant_id text, intent_version integer, consent_version integer, eligible boolean)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, privacy
AS $$
DECLARE
  v_actor text := privacy.actor();
BEGIN
  IF v_actor IS NULL THEN
    RAISE EXCEPTION 'unauthenticated' USING ERRCODE = 'GQ401';
  END IF;
  IF NOT (v_actor = ANY (p_participants)) OR cardinality(p_participants) > 5 THEN
    RAISE EXCEPTION 'forbidden' USING ERRCODE = 'GQ403';
  END IF;
  RETURN QUERY
    SELECT u.pid,
           i.intent_version,
           c.version,
           privacy.is_eligible(p_community, u.pid)
    FROM unnest(p_participants) AS u(pid)
    LEFT JOIN privacy.private_intents i
      ON i.community_id = p_community AND i.participant_id = u.pid
    LEFT JOIN privacy.current_consents c
      ON c.community_id = p_community AND c.participant_id = u.pid;
END
$$;

REVOKE ALL ON FUNCTION privacy.create_guest_session(bytea, interval) FROM PUBLIC;
REVOKE ALL ON FUNCTION privacy.resolve_session(bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION privacy.revoke_session(bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION privacy.is_eligible(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION privacy.authorized_candidates(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION privacy.member_versions(text, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION privacy.actor() TO gq_api;
GRANT EXECUTE ON FUNCTION privacy.create_guest_session(bytea, interval) TO gq_api;
GRANT EXECUTE ON FUNCTION privacy.resolve_session(bytea) TO gq_api;
GRANT EXECUTE ON FUNCTION privacy.revoke_session(bytea) TO gq_api;
GRANT EXECUTE ON FUNCTION privacy.authorized_candidates(text) TO gq_api;
GRANT EXECUTE ON FUNCTION privacy.member_versions(text, text[]) TO gq_api;

COMMIT;
