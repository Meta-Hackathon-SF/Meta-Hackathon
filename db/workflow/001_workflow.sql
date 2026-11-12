-- Kai-owned workflow persistence. Apply after db/privacy/001_privacy_foundation.sql.
-- API credentials are server-only and must be a non-owner member of gq_api.
-- A separate non-owner worker LOGIN also needs workflow_worker; never expose it to browsers.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'workflow_worker') THEN
    CREATE ROLE workflow_worker NOLOGIN;
  END IF;
END $$;

CREATE SCHEMA workflow;
REVOKE ALL ON SCHEMA workflow FROM PUBLIC;
GRANT USAGE ON SCHEMA workflow TO gq_api, workflow_worker;

CREATE TABLE workflow.quests (
  quest_id text PRIMARY KEY,
  community_id text NOT NULL REFERENCES privacy.communities(community_id),
  created_by text NOT NULL REFERENCES privacy.participants(participant_id),
  proposal_id text NOT NULL,
  proposal_revision integer NOT NULL CHECK (proposal_revision > 0),
  proposal jsonb NOT NULL,
  plan jsonb,
  revision integer NOT NULL CHECK (revision > 0),
  status text NOT NULL CHECK (status IN ('forming','proposed','planning','scheduled','revision_pending','completed','cancelled')),
  mode text NOT NULL CHECK (mode IN ('live','fixture','replay')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(proposal_id, proposal_revision)
);
CREATE TABLE workflow.quest_members (
  quest_id text NOT NULL REFERENCES workflow.quests ON DELETE CASCADE,
  participant_id text NOT NULL REFERENCES privacy.participants(participant_id),
  PRIMARY KEY(quest_id, participant_id)
);
CREATE TABLE workflow.acceptances (
  quest_id text NOT NULL REFERENCES workflow.quests ON DELETE CASCADE,
  participant_id text NOT NULL REFERENCES privacy.participants(participant_id),
  revision integer NOT NULL CHECK (revision > 0),
  choice text NOT NULL CHECK (choice IN ('accept','decline')),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(quest_id, participant_id, revision),
  FOREIGN KEY(quest_id, participant_id) REFERENCES workflow.quest_members
);
CREATE TABLE workflow.jobs (
  job_id text PRIMARY KEY,
  quest_id text NOT NULL REFERENCES workflow.quests ON DELETE CASCADE,
  revision integer NOT NULL CHECK (revision > 0),
  enqueued_by text NOT NULL REFERENCES privacy.participants(participant_id),
  member_versions jsonb NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','succeeded','failed')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  lease_owner text,
  lease_expires_at timestamptz,
  failure_code text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(quest_id, revision)
);
CREATE TABLE workflow.events (
  event_id text PRIMARY KEY,
  quest_id text NOT NULL UNIQUE REFERENCES workflow.quests ON DELETE CASCADE,
  conversation_id text NOT NULL UNIQUE,
  body jsonb NOT NULL
);
CREATE TABLE workflow.event_revisions (
  event_id text NOT NULL REFERENCES workflow.events ON DELETE CASCADE,
  revision integer NOT NULL,
  body jsonb NOT NULL,
  PRIMARY KEY(event_id, revision)
);
CREATE TABLE workflow.messages (
  message_id text PRIMARY KEY,
  quest_id text NOT NULL REFERENCES workflow.quests ON DELETE CASCADE,
  conversation_id text NOT NULL REFERENCES workflow.events(conversation_id) ON DELETE CASCADE,
  revision integer NOT NULL,
  text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 2000),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(conversation_id, revision)
);
CREATE TABLE workflow.outbox (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  quest_id text NOT NULL REFERENCES workflow.quests ON DELETE CASCADE,
  revision integer NOT NULL,
  event_id text NOT NULL UNIQUE,
  type text NOT NULL CHECK (type IN ('member.accepted','plan.proposed','event.created','message.created')),
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  payload jsonb NOT NULL
);
CREATE TABLE workflow.idempotency (
  participant_id text NOT NULL REFERENCES privacy.participants(participant_id),
  route text NOT NULL,
  key text NOT NULL CHECK (char_length(key) BETWEEN 1 AND 128),
  body_hash text NOT NULL,
  result jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(participant_id, route, key)
);

CREATE FUNCTION workflow.visible(p_quest text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, workflow, privacy
AS $$
 SELECT EXISTS (
  SELECT 1 FROM workflow.quests q JOIN workflow.quest_members m USING(quest_id)
  WHERE q.quest_id=p_quest AND m.participant_id=privacy.actor()
  AND privacy.is_eligible(q.community_id, privacy.actor())
 )
$$;
REVOKE ALL ON FUNCTION workflow.visible(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workflow.visible(text) TO gq_api, workflow_worker;

ALTER TABLE workflow.quests ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.quest_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.acceptances ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.event_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.idempotency ENABLE ROW LEVEL SECURITY;
-- No direct API access to jobs/private idempotency of other actors, and no API table writes.
CREATE POLICY quest_read ON workflow.quests FOR SELECT TO gq_api USING(workflow.visible(quest_id));
CREATE POLICY member_read ON workflow.quest_members FOR SELECT TO gq_api USING(workflow.visible(quest_id));
CREATE POLICY acceptance_read ON workflow.acceptances FOR SELECT TO gq_api USING(workflow.visible(quest_id));
CREATE POLICY event_read ON workflow.events FOR SELECT TO gq_api USING(workflow.visible(quest_id));
CREATE POLICY message_read ON workflow.messages FOR SELECT TO gq_api USING(workflow.visible(quest_id));
CREATE POLICY outbox_read ON workflow.outbox FOR SELECT TO gq_api USING(workflow.visible(quest_id));
CREATE POLICY idempotency_self ON workflow.idempotency TO gq_api
  USING(participant_id=privacy.actor()) WITH CHECK(participant_id=privacy.actor());
GRANT SELECT ON workflow.quests, workflow.quest_members, workflow.acceptances,
  workflow.events, workflow.messages, workflow.outbox TO gq_api;
GRANT SELECT, INSERT ON workflow.idempotency TO gq_api;

CREATE FUNCTION workflow.lock_quest(p_quest text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow, privacy
AS $$
DECLARE q workflow.quests; a jsonb; d jsonb;
BEGIN
  IF NOT workflow.visible(p_quest) THEN RAISE EXCEPTION 'not found' USING ERRCODE='GQ404'; END IF;
  SELECT * INTO q FROM workflow.quests WHERE quest_id=p_quest FOR UPDATE;
  SELECT COALESCE(jsonb_agg(participant_id ORDER BY participant_id),'[]') INTO a
    FROM workflow.acceptances WHERE quest_id=p_quest AND revision=q.revision AND choice='accept';
  SELECT COALESCE(jsonb_agg(participant_id ORDER BY participant_id),'[]') INTO d
    FROM workflow.acceptances WHERE quest_id=p_quest AND revision=q.revision AND choice='decline';
  RETURN to_jsonb(q) || jsonb_build_object('acceptedIds',a,'declinedIds',d);
END $$;

CREATE FUNCTION workflow.create_quest(p_id text, p_proposal jsonb, p_mode text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow, privacy
AS $$
DECLARE v_id text; v_member text; v_actor text := privacy.actor();
BEGIN
  IF v_actor IS NULL THEN RAISE EXCEPTION 'unauthenticated' USING ERRCODE='GQ401'; END IF;
  IF jsonb_array_length(p_proposal->'memberIds') NOT BETWEEN 3 AND 5
    OR NOT (p_proposal->'memberIds' ? v_actor)
    OR NOT privacy.is_eligible(p_proposal->>'communityId',v_actor) THEN
    RAISE EXCEPTION 'forbidden' USING ERRCODE='GQ403';
  END IF;
  INSERT INTO workflow.quests(quest_id,community_id,created_by,proposal_id,proposal_revision,proposal,revision,status,mode)
    VALUES(p_id,p_proposal->>'communityId',v_actor,p_proposal->>'proposalId',
      (p_proposal->>'revision')::integer,p_proposal,(p_proposal->>'revision')::integer,'forming',p_mode)
    ON CONFLICT(proposal_id,proposal_revision) DO NOTHING RETURNING quest_id INTO v_id;
  IF v_id IS NULL THEN
    SELECT quest_id INTO v_id FROM workflow.quests
      WHERE proposal_id=p_proposal->>'proposalId' AND proposal_revision=(p_proposal->>'revision')::integer;
    IF NOT workflow.visible(v_id) THEN RAISE EXCEPTION 'not found' USING ERRCODE='GQ404'; END IF;
    RETURN v_id;
  END IF;
  FOR v_member IN SELECT jsonb_array_elements_text(p_proposal->'memberIds') LOOP
    IF NOT privacy.is_eligible(p_proposal->>'communityId',v_member) THEN
      RAISE EXCEPTION 'consent required' USING ERRCODE='GQ403';
    END IF;
    INSERT INTO workflow.quest_members VALUES(v_id,v_member);
  END LOOP;
  RETURN v_id;
END $$;

CREATE FUNCTION workflow.save_plan(p_quest text, p_plan jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow, privacy
AS $$
DECLARE q workflow.quests;
BEGIN
  PERFORM workflow.lock_quest(p_quest);
  SELECT * INTO q FROM workflow.quests WHERE quest_id=p_quest;
  IF q.created_by<>privacy.actor() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='GQ403'; END IF;
  IF q.status NOT IN ('forming','proposed') THEN RAISE EXCEPTION 'stale' USING ERRCODE='GQ409'; END IF;
  IF (p_plan->>'revision')::integer < q.revision THEN RAISE EXCEPTION 'stale' USING ERRCODE='GQ409'; END IF;
  -- A voted revision is immutable, including non-material opener/rationale edits.
  IF (p_plan->>'revision')::integer=q.revision AND p_plan IS DISTINCT FROM q.plan
    AND EXISTS(SELECT 1 FROM workflow.acceptances WHERE quest_id=p_quest AND revision=q.revision) THEN
    RAISE EXCEPTION 'voted revision is immutable' USING ERRCODE='GQ409';
  END IF;
  UPDATE workflow.quests SET plan=p_plan,revision=(p_plan->>'revision')::integer,status='proposed' WHERE quest_id=p_quest;
  INSERT INTO workflow.outbox(quest_id,revision,event_id,type,payload)
    VALUES(p_quest,(p_plan->>'revision')::integer,'wf_'||replace(gen_random_uuid()::text,'-',''),
      'plan.proposed',jsonb_build_object('questId',p_quest));
END $$;

CREATE FUNCTION workflow.record_acceptance(p_quest text,p_revision integer,p_choice text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow, privacy
AS $$
DECLARE q workflow.quests; a workflow.acceptances; n integer; existing boolean;
BEGIN
  PERFORM workflow.lock_quest(p_quest);
  SELECT * INTO q FROM workflow.quests WHERE quest_id=p_quest;
  IF p_revision<>q.revision OR p_choice NOT IN ('accept','decline') THEN
    RAISE EXCEPTION 'stale' USING ERRCODE='GQ409';
  END IF;
  SELECT * INTO a FROM workflow.acceptances WHERE quest_id=p_quest
    AND participant_id=privacy.actor() AND revision=p_revision;
  existing := FOUND;
  IF existing THEN
    IF a.choice<>p_choice THEN RAISE EXCEPTION 'stale' USING ERRCODE='GQ409'; END IF;
  ELSE
    IF q.status<>'proposed' THEN RAISE EXCEPTION 'stale' USING ERRCODE='GQ409'; END IF;
    INSERT INTO workflow.acceptances(quest_id,participant_id,revision,choice)
      VALUES(p_quest,privacy.actor(),p_revision,p_choice) RETURNING * INTO a;
    INSERT INTO workflow.outbox(quest_id,revision,event_id,type,payload)
      VALUES(p_quest,p_revision,'wf_'||replace(gen_random_uuid()::text,'-',''),
        'member.accepted',jsonb_build_object('participantId',privacy.actor(),'choice',p_choice));
  END IF;
  SELECT count(*) INTO n FROM workflow.acceptances
    WHERE quest_id=p_quest AND revision=p_revision AND choice='accept';
  IF n>5 THEN RAISE EXCEPTION 'capacity' USING ERRCODE='GQ410'; END IF;
  IF n>=3 AND q.status='proposed' THEN
    UPDATE workflow.quests SET status='planning' WHERE quest_id=p_quest;
    INSERT INTO workflow.jobs(job_id,quest_id,revision,enqueued_by,member_versions)
      VALUES('job_'||replace(gen_random_uuid()::text,'-',''),p_quest,p_revision,
        privacy.actor(),q.plan->'memberVersions') ON CONFLICT(quest_id,revision) DO NOTHING;
  END IF;
  RETURN jsonb_build_object('questId',p_quest,'participantId',a.participant_id,
    'revision',a.revision,'choice',a.choice,'recordedAt',to_char(a.recorded_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
END $$;

CREATE FUNCTION workflow.claim_job(p_worker text,p_seconds integer) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow
AS $$
DECLARE j workflow.jobs;
BEGIN
  IF p_seconds NOT BETWEEN 1 AND 300 OR char_length(p_worker) NOT BETWEEN 1 AND 128 THEN
    RAISE EXCEPTION 'invalid lease' USING ERRCODE='GQ400';
  END IF;
  SELECT * INTO j FROM workflow.jobs WHERE
    (status='pending' OR (status='running' AND lease_expires_at<clock_timestamp()))
    AND attempts<5 ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN NULL; END IF;
  UPDATE workflow.jobs SET status='running',attempts=attempts+1,lease_owner=p_worker,
    lease_expires_at=clock_timestamp()+make_interval(secs=>p_seconds)
    WHERE job_id=j.job_id RETURNING * INTO j;
  RETURN to_jsonb(j) || (SELECT jsonb_build_object('community_id',q.community_id,
    'plan',q.plan,'proposal',q.proposal,'mode',q.mode) FROM workflow.quests q WHERE q.quest_id=j.quest_id);
END $$;

CREATE FUNCTION workflow.lock_job(p_job text,p_worker text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow
AS $$
DECLARE j workflow.jobs;
BEGIN
  SELECT * INTO j FROM workflow.jobs WHERE job_id=p_job FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'not found' USING ERRCODE='GQ404'; END IF;
  IF j.lease_owner IS DISTINCT FROM p_worker OR j.status NOT IN ('running','succeeded')
    OR (j.status='running' AND j.lease_expires_at<=clock_timestamp()) THEN
    RAISE EXCEPTION 'stale lease' USING ERRCODE='GQ409';
  END IF;
  RETURN to_jsonb(j) || (SELECT jsonb_build_object('community_id',q.community_id,
    'plan',q.plan,'proposal',q.proposal,'mode',q.mode) FROM workflow.quests q WHERE q.quest_id=j.quest_id);
END $$;

CREATE FUNCTION workflow.finish_job(p_job text,p_worker text,p_plan jsonb,p_material boolean)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow, privacy
AS $$
DECLARE j workflow.jobs; q workflow.quests; accepted jsonb; e_id text; c_id text; e_body jsonb;
BEGIN
  PERFORM workflow.lock_job(p_job,p_worker);
  SELECT * INTO j FROM workflow.jobs WHERE job_id=p_job;
  SELECT * INTO q FROM workflow.quests WHERE quest_id=j.quest_id FOR UPDATE;
  IF j.status='succeeded' THEN RETURN q.quest_id; END IF;
  IF q.status<>'planning' OR q.revision<>j.revision OR privacy.actor()<>j.enqueued_by THEN
    RAISE EXCEPTION 'stale' USING ERRCODE='GQ409';
  END IF;
  IF p_material THEN
    UPDATE workflow.quests SET status='proposed',revision=q.revision+1,
      plan=p_plan || jsonb_build_object('revision',q.revision+1,'basedOnRevision',q.revision)
      WHERE quest_id=q.quest_id;
    UPDATE workflow.jobs SET status='succeeded' WHERE job_id=p_job;
    RETURN q.quest_id;
  END IF;
  SELECT jsonb_agg(participant_id ORDER BY participant_id) INTO accepted
    FROM workflow.acceptances WHERE quest_id=q.quest_id AND revision=q.revision AND choice='accept';
  IF jsonb_array_length(accepted) NOT BETWEEN 3 AND 5 THEN
    RAISE EXCEPTION 'stale' USING ERRCODE='GQ409';
  END IF;
  e_id := 'event_'||replace(gen_random_uuid()::text,'-','');
  c_id := 'conversation_'||replace(gen_random_uuid()::text,'-','');
  SELECT event_id,conversation_id INTO e_id,c_id FROM workflow.events WHERE quest_id=q.quest_id;
  IF NOT FOUND THEN
    e_id := 'event_'||replace(gen_random_uuid()::text,'-','');
    c_id := 'conversation_'||replace(gen_random_uuid()::text,'-','');
  END IF;
  e_body := jsonb_build_object('eventId',e_id,'questId',q.quest_id,'planId',p_plan->>'planId',
    'revision',q.revision,'status','scheduled','title',p_plan->>'title','venueId',p_plan->>'venueId',
    'start',p_plan->>'start','end',p_plan->>'end','acceptedMemberIds',accepted,'conversationId',c_id);
  INSERT INTO workflow.events VALUES(e_id,q.quest_id,c_id,e_body)
    ON CONFLICT(quest_id) DO UPDATE SET body=EXCLUDED.body;
  INSERT INTO workflow.event_revisions VALUES(e_id,q.revision,e_body) ON CONFLICT DO NOTHING;
  INSERT INTO workflow.messages(message_id,quest_id,conversation_id,revision,text)
    VALUES('message_'||replace(gen_random_uuid()::text,'-',''),q.quest_id,c_id,q.revision,p_plan->>'opener')
    ON CONFLICT(conversation_id,revision) DO NOTHING;
  INSERT INTO workflow.outbox(quest_id,revision,event_id,type,payload)
    VALUES(q.quest_id,q.revision,'wf_'||replace(gen_random_uuid()::text,'-',''),'event.created',e_body);
  UPDATE workflow.quests SET status='scheduled',plan=p_plan WHERE quest_id=q.quest_id;
  UPDATE workflow.jobs SET status='succeeded' WHERE job_id=p_job;
  RETURN q.quest_id;
END $$;

CREATE FUNCTION workflow.fail_job(p_job text,p_worker text,p_code text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, workflow
AS $$ BEGIN
  PERFORM workflow.lock_job(p_job,p_worker);
  UPDATE workflow.jobs SET status='failed',failure_code=p_code,lease_expires_at=NULL
    WHERE job_id=p_job AND status='running';
END $$;

-- All application mutation functions require a verified actor through privacy.actor().
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA workflow FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workflow.visible(text),workflow.lock_quest(text),
  workflow.create_quest(text,jsonb,text),workflow.save_plan(text,jsonb),
  workflow.record_acceptance(text,integer,text) TO gq_api;
-- Claim, completion and lease metadata never belong to ordinary API credentials.
GRANT EXECUTE ON FUNCTION workflow.claim_job(text,integer),workflow.lock_job(text,text),
  workflow.finish_job(text,text,jsonb,boolean),workflow.fail_job(text,text,text) TO workflow_worker;
COMMIT;
