# Meta Closer Together with AI — frontend

An unofficial Facebook-style frontend prototype, built with React, TypeScript,
Vite, Tailwind CSS v4, React Router, and Lucide React. All people, communities,
posts, listings, and events are fictional demonstration content.

## Run locally

Use Node.js 22.12+ and npm (validated with Node 22.20.0).
From the repository root:

```sh
cd web
npm ci
npm run dev
```

Open the local URL printed by Vite. No backend, login, API keys, or environment
variables are needed. Images are served locally from `public/demo/`; see
[ASSETS.md](ASSETS.md) for sources.

## What works

- A responsive desktop feed with sticky navigation, sidebars, stories, and contacts.
- A mobile layout with a compact header, full-width posts, and floating bottom tabs.
- 14 typed mock posts, including text, long text, single photos, photo grids,
  community posts, and an event card.
- Like/unlike, comments, expanding post text, post menus, saving/hiding posts,
  sharing, photo previews, and a story viewer.
- Post creation with an audience selector and up to four local image attachments.
- Search by post text, author, or community; account, notification, and Messenger menus.

Posts, likes, comments, saved posts, and hidden posts use the localStorage key
`closer-together-feed-v1`. Clear that key to reset the feed. The prototype remains
usable in memory when localStorage is unavailable; large photo attachments may
exceed the browser's storage quota. Chat previews and secondary-page selections
are temporary page state.

## Routes

`/`, `/friends`, `/groups`, `/marketplace`, `/watch`, `/events`, `/saved`,
`/memories`, `/profile`, `/messages`, `/notifications`, and `/campus`.

Home is the main implementation. Secondary routes are lightweight demo surfaces.
Campus is a modular placeholder; college communities, class chats, housing, and
other Campus product features have not been implemented.

## Validation

```sh
npm run lint
npm run build
npm run test:e2e
npm run screenshots -- review
npm run preview
```

The build runs TypeScript checks before generating `dist/`. Oxlint checks source,
test, and script files. Playwright runs desktop and mobile smoke tests for
rendering, local images, navigation/direct route visits, likes, post creation,
comments, saved posts, search, menus, stories, sharing, photo attachments, and
responsive overflow.

On Windows the browser checks use installed Google Chrome. On other platforms,
install Playwright's Chromium browser once with `npx playwright install chromium`.
Set `PLAYWRIGHT_CHANNEL` to use another installed Chromium browser channel.

The test runner starts Vite automatically unless an existing server is available
on port 5173. The screenshot script requires a running server (`npm run dev`);
optionally set `PREVIEW_URL` to capture a different local server.

Screenshot output is ignored by Git and saved in `artifacts/visual/<round>/` at:

- 1440×900 desktop
- 1280×800 laptop
- 768×1024 tablet
- 390×844 mobile
- 375×812 small mobile

Each round also captures the first post's action bar and writes layout/error
metrics. Automated responsive checks additionally cover 428px width.

## Structure

```text
public/demo/              Locally served stock photos and portraits
src/
  components/
    common/              Avatar, icon button, accessible native dialog
    feed/                Composer, create-post modal, post card
    layout/              Desktop sidebars
    navigation/          Header, mobile tabs, shared navigation definitions
    stories/             Story rail and viewer
  data/demo.ts           Fictional typed posts, people, stories, notifications
  layouts/               Shared shell and secondary-page frame
  pages/                 Home, modular Campus placeholder, secondary demos
  state/                 Shared React context and browser persistence
  types/feed.ts          Author, Post, Comment, and image types
  assets/                Reserved for future imported assets
  App.tsx                Routes
  index.css              Tailwind v4 import, theme, and responsive styles
tests/feed.spec.ts        Playwright smoke tests
scripts/capture-ui.mjs    Repeatable screenshot capture
```

Tailwind v4 remains configured with `@tailwindcss/vite` in `vite.config.ts`
and `@import "tailwindcss"` in `src/index.css`.

## Visual reference notes

The requested `references/facebook-desktop.png` and
`references/facebook-mobile.png` were not present. The implementation uses the
desktop screenshots attached to the request and the six supplied mobile photos.
Facebook's unauthenticated public page redirects to login.

The reference desktop home has an empty feed; this prototype intentionally adds
the requested stories and populated feed. Remaining differences include stock
demo imagery, system typography, and Lucide icons in place of Facebook's
proprietary font/icon assets. Device status bars and the iOS home indicator are
browser/OS chrome and are not simulated. Secondary pages are placeholders rather
than complete reproductions; the reel preview does not play a video.

## Vercel

Set the Vercel project's **Root Directory** to `web`. `vercel.json` configures
Vite, `npm ci`, `npm run build`, and `dist` output. Its SPA rewrite routes client
paths to `/index.html`, supporting direct visits and refreshes.

The project is ready for review and Vercel configuration. Local commits are on
the feature branch; nothing has been pushed or deployed.
