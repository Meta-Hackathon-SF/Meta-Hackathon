# Reliable event orchestration system: owned by kai
Read root AGENTS.md, docs/roles/kai.md and all shared contracts.
Assigned branch: `role/kai-orchestration`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Own durable state transitions and real-time delivery so model-generated proposals produce one correct event even under retries and simultaneous users.
Keep this feature UI independent of the mock Facebook shell; scope styles and expose documented component props for Will's composition.
