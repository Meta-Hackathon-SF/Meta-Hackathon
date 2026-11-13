# Frontend deployment on Vercel

Run the frontend build with the repository root available. Shared types live at
`contracts/protocol.ts`, outside `web/`. Uploading only `web/` removes those types
and causes TS2307 plus secondary implicit-any and FollowUp property errors.

Use the root `vercel.json` with these project settings:

| Setting | Value |
| --- | --- |
| Root Directory | Repository root (`./`); clear the existing `web` value |
| Framework Preset | Vite |
| Node.js | 22.x |
| Install Command | `npm ci --prefix web` |
| Build Command | `npm run build --prefix web` |
| Output Directory | `web/dist` |

Clear conflicting dashboard overrides or set them to the values above. Deploy
the commit containing the root config, with build cache disabled for the first
retry. For a CLI upload, run Vercel from the repository root, not from `web/`.
The existing `web/vercel.json` is preserved for its owner; the root config
preserves its SPA rewrite, so deep links serve `index.html`.

The alternative for a Git-connected project retaining Root Directory `web` is
Vercel's **Include source files outside of the Root Directory in the Build
Step** setting. A CLI upload containing only `web/` still lacks the contracts;
prefer the repository-root configuration above.

Preserve the existing public `VITE_CONSTELLATIONS_API` value for a live backend.
Without it the frontend uses its labeled fixture mode. Keep model keys and
database/session secrets on the API host. This config deploys the frontend;
FastAPI remains a separately hosted service.

## Verification

At base main `fb811b0`, a clean tracked-files upload of only `web/` reproduced
TS2307, TS7006, TS2339, TS2353 and TS2322, including the reported FollowUp errors.
Restoring `contracts/` to the same upload made the unchanged build pass.
A separate fresh role worktree passed the exact install/build commands above
using Node 22.20.0 and npm 10.9.3 on Windows. TypeScript checks remain enabled.
Relative-import spelling/case and the unchanged SPA rewrite were also checked.
This is not a Linux or remote Vercel deployment result.

The local project link exists, but no Vercel token/CLI login was available to
inspect remote settings or logs. Confirm the next deployment reports Ready,
then open `/`, refresh `/space` and `/space/operator`, and check asset loading
and browser errors before calling the remote deployment fixed.

References: [Vercel build configuration](https://vercel.com/docs/builds/configure-a-build)
and [shared sources outside the root](https://vercel.com/docs/monorepos/monorepo-faq).
