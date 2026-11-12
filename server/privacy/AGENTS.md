# Privacy, consent and output guard: owned by patrik
Read root AGENTS.md, docs/roles/patrik.md and all shared contracts.
Assigned branch: `role/patrik-privacy`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Constellations: own ConsentV2 (3 toggles incl. 18+), answers readable only by author and server, blocks, M1 safety triage, the output guard (no-quote 5+ word checker, sensitive-term filter), Sky threshold (3 demo / 25 prod), deletion + 14-day TTL, and the prompt builder that strips all profile fields. Adapts the merged sessions, consent and projections. Target contract: contracts/constellations.ts (2.0.0-proposed, D009).
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
