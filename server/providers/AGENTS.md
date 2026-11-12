# Single Muse adapter: owned by adam
Read root AGENTS.md, docs/roles/adam.md and all shared contracts.
Assigned branch: `role/adam-planning`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Constellations: the single Muse provider adapter (live-verified model muse-spark-1.3) used by every Keeper job M1-M8; strict JSON, one retry, labeled fallback, sanitized ModelEvidence with callType and latency. Never invent provider APIs. Target contract: contracts/constellations.ts (2.0.0-proposed, D009).
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
