# Reliable event orchestration system: owned by kai
Read root AGENTS.md, docs/roles/kai.md and all shared contracts.
Assigned branch: `role/kai-orchestration`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Own durable state transitions and real-time delivery so model-generated proposals produce one correct event even under retries and simultaneous users.
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
