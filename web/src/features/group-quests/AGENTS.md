# Group Quests feature boundary
The existing web application is the mock Facebook host UI. This feature gets its own UI.
Read root AGENTS.md and the named owner document before editing.
- onboarding/ and shell/: Will
- matching/: Rishi
- planning/: Adam
- privacy/: Patrik
- events/: Kai
No production feature components are scaffolded yet; these are ownership boundaries.
Will integrates the proposed route /groups/:communityId/quests into existing App.tsx and navigation after inspecting the shell.
Owners export documented components/hooks. Do not rewrite shared feed/layout files or global CSS as part of a feature module. Use scoped feature styling. Do not use the shell's demo users or localStorage as authenticated backend state.
