# Confession capture: owned by will
Read root AGENTS.md, docs/roles/will.md and all shared contracts.
Assigned branch: `role/will-voice-ui`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Constellations: own confession capture by voice (transcribed) or text, 1-400 characters, with typed fallback that never loses the session; reuses the merged transcription adapter and onboarding. Will composes the join, confession, follow-up and guess flow. Target contract: contracts/constellations.ts (2.0.0-proposed, D009).
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
