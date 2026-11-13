# TEST-ONLY proposed v3 sky

Standalone synthetic fixture, draft types and strict validators. No production imports, routes, live APIs, model calls or participant data. Contract 2.1 remains active; this does not claim an accepted v3 contract or integrated backend.

From `web/`, run the single focused suite:

```powershell
npx playwright test --config src/features/constellations/sky/test-only/v3/playwright.config.ts
```

For local review on the dedicated port:

```powershell
node node_modules/vite/bin/vite.js --config src/features/constellations/sky/test-only/v3/vite.config.ts
```

Open `http://127.0.0.1:5194/`. Saturday draws 10,000 fixed positions with no zoom, five day colors, own-star ring and second-degree lines at 25% opacity. Whole-week/day filtering and second-degree visibility are local preview controls. The forming tab is explicitly an illustrative visualization. Sunday shows four synthetic anchors on an illustrative infinity path, with no chat or real formation claim.

Verified locally: the focused command above passed **2 tests** in **5.8 seconds**, using installed Google Chrome (`channel: 'chrome'`) on port 5194. The initial attempt with bundled Chromium passed validation but could not launch the browser because Playwright's browser download was absent. The final run covers desktop and 390px mobile rendering, controls, no wheel zoom, visible fixture labels, progress animation and invalid/private payload rejection. Screenshots are written into this directory's `artifacts/` folder. Root review also passed web lint/build. Lint warnings remain in existing Will-owned files. The full application E2E run is recorded separately in Kai's handoff.

Positions use explicitly decoded little-endian signed 16-bit pairs on 0..32767. Validators enforce byte length = count × 4, index/grid bounds, day/color agreement, own membership, neighbor linkage, two sets per neighbor, 40-set/3,000-star caps and strict field allowlists at every object level. Extra private fields are rejected rather than stripped. Star indices are synthetic cycle-local indices, never participant identifiers.
