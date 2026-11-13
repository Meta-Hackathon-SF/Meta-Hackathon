# Proposed v3 sky preview

This synthetic preview covers the Saturday sky, a labeled formation visualization
and illustrative Sunday Meta-logo anchors. Production uses contract 2.1.0 while
Rishi prepares the approved 3.0.0 shapes.

Run from web/ with the following command.

```sh
npx playwright test --config src/features/constellations/sky/test-only/v3/playwright.config.ts
```

For interactive review, run the preview server and open http://127.0.0.1:5194/.

```sh
node node_modules/vite/bin/vite.js --config src/features/constellations/sky/test-only/v3/vite.config.ts
```

The Canvas renders 10,000 fixed synthetic positions, five day colors, the viewer's
star marker and second-degree lines at 25% opacity. Preview controls select days and
scenes. Formation is labeled as illustrative. Sunday uses four synthetic anchors
on an infinity path. A frame-rate benchmark and live producer integration remain
pending.

Draft validators enforce case-sensitive field allowlists, base64 byte length,
little-endian 16-bit positions, grid/index bounds, day/color agreement, own
membership, neighbor links and second-degree caps. Chrome is selected on Windows;
other platforms use Playwright's bundled Chromium. Screenshots go to the ignored
artifacts/ directory. Actual commands and results are recorded in Kai's handoff.
