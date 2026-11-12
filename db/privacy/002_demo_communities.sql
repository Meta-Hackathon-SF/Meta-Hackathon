-- DEMO community metadata (owner: Patrik). Public, non-private rows only.
-- IDs and areas match Will's SIMULATED shell communities
-- (web/src/features/group-quests/shell/communities.ts on role/will-voice-ui)
-- so the feature route can join them. is_demo marks them as demo data.
INSERT INTO privacy.communities (community_id, name, area_ids, currency, is_demo) VALUES
  ('demo-campus', 'Demo Campus (synthetic)', ARRAY['demo-campus-central'], 'USD', true),
  ('hackathon-builders', 'Hackathon Builders Community',
     ARRAY['main-quad', 'engineering-plaza', 'downtown-library'], 'USD', true),
  ('meta-ai-explorers', 'Meta AI Explorers', ARRAY['main-quad', 'student-union'], 'USD', true),
  ('xr-student-collective', 'XR Student Collective', ARRAY['media-lab', 'student-union'], 'USD', true)
ON CONFLICT (community_id) DO NOTHING;
