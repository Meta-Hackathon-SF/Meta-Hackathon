# Frontend validation — November 12, 2026

Implementation reviewed on `feat/facebook-ui`, using Node 22.20.0, npm 10.9.3,
and local Google Chrome through Playwright.

## Results

- `npm run lint`: passed, no warnings.
- `npm run build`: passed TypeScript checks and Vite production compilation.
- `npm run test:e2e`: **16 passed** across desktop and mobile projects.
- All 16 local photo assets decoded successfully in the browser.
- Production preview checks passed at 1440px and 390px widths for all 12 routes,
  direct navigation, image rendering, and like persistence through refresh.
- No horizontal overflow, broken images, or browser errors in the captured layouts.
- Vercel configuration retains `web` as the project root, Vite build output in
  `dist`, and a catch-all SPA rewrite to `/index.html`. No deployment was performed.

## Visual review

Three rounds of screenshots were captured and opened for visual inspection.
All rounds cover 1440×900, 1280×800, 768×1024, 390×844, and 375×812.
Automated responsive checks also cover 428px width.

The first pass established the desktop feed at 680px, centered at x=380 on a
1440px viewport, with a 56px sticky header. The second pass reduced the mobile
wordmark width, tightened the composer/story spacing, shortened the first demo
caption, and corrected the filled Home and grid menu icons. The third pass
refined story clipping, timestamp typography, action target sizes, and mobile
scroll margins. Scrolled screenshots were also inspected for post actions,
reaction counts, card separators, and the fixed mobile navigation.

The capture script waits for Chromium to paint sticky elements after scrolling
to avoid a transient screenshot artifact. Use `npm run screenshots -- review`
with Vite running to reproduce the final screenshots in
`artifacts/visual/review/`. Screenshot output is local and ignored by Git.

## Automated interaction coverage

The eight scenarios run on both desktop and mobile:

1. Home rendering, 14 typed posts, local images, and no runtime errors.
2. Like/unlike with counts and persistence through refresh.
3. Empty-post validation, post creation, feed insertion, and persistence.
4. Comments, expanded/collapsed text, and saved-post navigation.
5. Navigation and direct visits to every secondary route.
6. Search, Messenger, account/menu controls, and notifications.
7. Responsive rendering and overflow at 375, 390, 428, and 768px.
8. Story/photo dialogs, Escape handling, sharing, and local photo attachments.

## Remaining visual and scope differences

The named `web/references/facebook-desktop.png` and `facebook-mobile.png` files
were absent. The supplied inline desktop screenshots and six mobile images were
used instead. The public Facebook page provided no authenticated feed context.

The desktop reference has an empty feed; the prototype adds the requested stories
and fictional posts. Locally stored stock photos, system typography, and Lucide
icons replace Facebook's original content and proprietary assets. Native phone
status bars and the iOS home indicator are not reproduced in the web page.

Secondary routes intentionally contain small demo surfaces. Video playback,
real messaging, profile editing, backend/authentication, and the Campus product
are outside this implementation.
