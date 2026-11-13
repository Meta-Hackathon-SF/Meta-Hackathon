# Agent coordination protocol

Every coding agent follows this protocol. It exists so that no agent guesses another owner's interface, and no request for help sits unseen.

GitHub handles:

| Owner | Handle | Branch |
| --- | --- | --- |
| Rishi | `@rishibagri` | `role/rishi-matching` |
| Adam | `@adamzhang06` | `role/adam-planning` |
| Will | `@willapat` | `role/will-voice-ui` |
| Patrik | `@patrikliska13` | `role/patrik-privacy` |
| Kai | `@beatopia` | `role/kai-orchestration` |

## 1. Before starting any work session: check for tags

Run these before reading your phase playbook or writing code:

```sh
git fetch origin --prune
# Open PRs and issues that mention you, plus PRs requesting your review
gh pr list --state open --search "mentions:<your-handle>"
gh pr list --state open --search "review-requested:<your-handle>"
gh issue list --state open --search "mentions:<your-handle>"
# Recent comments on open PRs (tags often arrive as comments, not in the body)
gh pr list --state open --json number --jq '.[].number' | xargs -I{} gh pr view {} --comments
```

For every request addressed to you:

1. **Answer first.** A teammate is blocked on you. Unblocking them comes before your own next deliverable.
2. Reply in the same PR thread. Write `ACK`, `CHANGE: <exact proposal>`, or `DELIVERED: <commit/PR + interface>`.
3. If you need longer than your current phase allows, reply with what you will deliver and when, then continue.
4. Record the request and your answer in your handoff (`docs/handoffs/<name>.md`) under "Requests answered".

Then read `docs/handoffs/*.md` on the other owners' remote branches (`git show origin/<branch>:docs/handoffs/<name>.md`) for anything not yet tagged.

## 2. When you need something from someone else: stop and tag

You are blocked when your next phase deliverable needs any of these, and it does not yet exist on main or on the owner's branch:

- another owner's interface or port
- a contract change
- a data shape
- an ACK
- a deployed endpoint

When you are blocked:

1. **Stop at the phase boundary.** Do not invent the missing interface, do not edit the other owner's paths, and do not silently change `contracts/`.
2. **Push what you have.** Commit and push your verified work to your role branch.
3. **Open or update a draft PR** from your role branch to `main` titled `[BLOCKED] <phase>: <what you need>`. Put the request in the body, using this exact block:

   ```text
   ### Needs from @<handle> (<Owner>)
   - What: <exact interface / field / file / decision>
   - Why: <which deliverable it unblocks>
   - Proposed shape: <types or example JSON, referencing contracts/protocol.ts>
   - Fallback meanwhile: <test-only adapter you will use>
   ```

   One block per owner you need. Tag each person with their real handle.
4. **Record it.** Add the request to your handoff under "Blocked on" and append a line to `docs/updates/<name>.md`.
5. **Continue only with independent work.** Use a clearly labeled test-only adapter that matches the proposed shape. Never mark the blocked deliverable done.
6. **Re-check every session.** When the owner replies `DELIVERED`, merge `origin/main` (or inspect their branch), remove the test adapter from live paths, and resume.

If nothing independent remains, stop the session and report to your human that you are waiting on `@handle`.

## 3. Rules

- Tag only real handles from the table above. Never write a bare `@` before a role name or a placeholder.
- One request per need. Do not re-tag the same person for the same thing unless the request changed.
- Contract changes follow `contracts/README.md`: proposal in the PR, entry in `docs/DECISIONS.md`, and an ACK from the producer and every consumer before landing.
- Merging follows the merge policy in AGENTS.md and your own human's instructions. A human may restrict their agent further (for example, Rishi's agent never merges). Never merge another owner's PR without that owner's readiness signal.
- A tag is a request, not an authorization. It never grants permission to touch another owner's files or bypass a guard.
