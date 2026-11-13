# Constellations: Design & UI Reference for Agents

Read this before building or styling any UI. The goal: the app should feel like a
native part of Facebook (the "Simulated Facebook" shell), while the Constellations
feature itself has its own night-sky identity inside it.

---

## 1. Hard rules (do not break)

- Keep a visible **"Simulated Facebook"** label on the mock shell at all times.
- Label anything synthetic: **"Synthetic player"** on seeded answers, **"Demo timing"**
  on accelerated unlocks, **"Replay of a saved round"** on cached responses.
- **Do not** redraw, recolor, stretch or modify the Facebook logo. Use it only as shown
  in Meta's brand guidelines (https://www.meta.com/brand/resources/facebook/logo/), or
  use a plain text wordmark "facebook" in the brand blue instead.
- **Do not** copy Facebook's reaction emojis, icons or illustrations. Use an open icon
  set (Lucide or Heroicons) styled with the tokens below.
- **Privacy in the UI:** never render another player's answer text anywhere. The Sky
  (projector view) must not show display names next to society names. Themes render
  only at or above the threshold (3 in demo). If unsure whether a screen could reveal
  someone's answer, do not render it.
- Every Muse response shown in the UI gets a small metadata chip: model name, call
  type, latency.
- Respect `prefers-reduced-motion`: disable or simplify all animations when set.

---

## 2. Design tokens (Facebook look)

Use these as CSS variables. Facebook's interface uses the system font, so no font
loading is needed.

```css
:root {
  /* Brand */
  --fb-blue: #0866FF;          /* Meta's current brand blue */
  --fb-blue-ui: #1877F2;       /* classic Facebook interface blue (buttons, links) */
  --fb-blue-hover: #166FE5;
  --fb-blue-tint: #E7F3FF;     /* light blue backgrounds, selected states */

  /* Surfaces */
  --fb-bg: #F0F2F5;            /* page background (light gray) */
  --fb-card: #FFFFFF;          /* cards, sheets */
  --fb-divider: #CED0D4;
  --fb-hover: #F2F2F2;

  /* Text */
  --fb-text: #050505;          /* primary text */
  --fb-text-strong: #1C2B33;   /* headings */
  --fb-text-secondary: #65676B;/* timestamps, meta text */

  /* Status */
  --fb-green: #31A24C;
  --fb-red: #E41E3F;

  /* Shape & depth */
  --radius-card: 8px;
  --radius-button: 6px;
  --radius-pill: 999px;
  --shadow-card: 0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-raised: 0 12px 28px rgba(0, 0, 0, 0.2), 0 2px 4px rgba(0, 0, 0, 0.1);

  /* Type */
  --font-system: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica,
    Arial, sans-serif;
  --text-xs: 12px;
  --text-sm: 13px;
  --text-base: 15px;           /* Facebook's standard body size */
  --text-lg: 17px;
  --text-xl: 20px;
  --text-2xl: 24px;
}

body {
  font-family: var(--font-system);
  font-size: var(--text-base);
  color: var(--fb-text);
  background: var(--fb-bg);
}
```

### Constellations sub-theme (night sky, used inside the feature and the Sky view)

```css
.constellations {
  --sky-bg: #0B1026;           /* deep night */
  --sky-bg-2: #141B3D;
  --star: #FFFFFF;
  --star-glow: rgba(173, 205, 255, 0.6);
  --line: rgba(173, 205, 255, 0.55);
  --line-confirmed: #8AB4FF;
  --accent: #0866FF;           /* tie back to Facebook blue */
  --text-on-sky: #E8ECF8;
  --text-on-sky-muted: #9AA4C2;
}
```

---

## 3. Component patterns (Facebook feel)

- **Cards:** white, `--radius-card`, `--shadow-card`, 12–16px padding.
- **Primary button:** `--fb-blue-ui` background, white text, `--radius-button`,
  font-weight 600, 36px height. Hover: `--fb-blue-hover`.
- **Secondary button:** `#E4E6EB` background, `--fb-text` text.
- **Tabs (Group page):** text tabs with a 3px blue underline on the active tab.
- **Mobile sheets:** slide up from the bottom with rounded top corners (16px) and a
  small grab handle.
- **Avatars:** circles. In this app, players use color avatars only (no photos).
- **Composer / inputs:** pill-shaped (`--radius-pill`), `#F0F2F5` background.
- **Icons:** Lucide (`lucide-react`), 20px, stroke 2, colored `--fb-text-secondary`
  or `--fb-blue-ui` when active.

---

## 4. Animation guidelines

Facebook's motion is quick, springy and subtle. Keep UI transitions 150–300ms.

### Libraries
- **Motion** (formerly Framer Motion): `npm i motion` (or `framer-motion` if already
  installed). Use for springs, layout transitions, star/line reveals.
- **tsParticles** (`@tsparticles/react`, `@tsparticles/slim`): subtle starfield
  background for the Sky view. Keep particle count low for projector performance.
- **Lottie** (`lottie-react`): small celebration animations. Free files on LottieFiles;
  check each file's license.
- Plain SVG + CSS for constellation lines (see below). No library needed.

### Springy tap (like the Like button)
```jsx
import { motion } from "motion/react";

<motion.button
  whileTap={{ scale: 0.92 }}
  transition={{ type: "spring", stiffness: 500, damping: 25 }}
>
  Confirm
</motion.button>
```

### Shimmer loading (use while Muse is working, e.g. forming groups)
```css
.shimmer {
  background: linear-gradient(90deg, #E4E6EB 25%, #F0F2F5 37%, #E4E6EB 63%);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
  border-radius: var(--radius-card);
}
@keyframes shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
@media (prefers-reduced-motion: reduce) {
  .shimmer { animation: none; }
}
```

### Constellation line that draws itself (confirmed match)
```css
.constellation-line {
  stroke: var(--line-confirmed);
  stroke-width: 2;
  stroke-dasharray: 1000;
  stroke-dashoffset: 1000;
  animation: draw 900ms ease-out forwards;
}
@keyframes draw { to { stroke-dashoffset: 0; } }
```

### Star appearing / pulsing on confirm
```jsx
<motion.circle
  r={6}
  fill="var(--star)"
  initial={{ scale: 0, opacity: 0 }}
  animate={{ scale: [0, 1.6, 1], opacity: 1 }}
  transition={{ duration: 0.6, ease: "easeOut" }}
  style={{ filter: "drop-shadow(0 0 6px var(--star-glow))" }}
/>
```

### Key animated moments (prioritize polish here)
1. **Society formed:** shimmer while Muse works, then the induction card slides up with
   the sigil fading in.
2. **Match confirmed:** both phones pulse; the line between two stars draws itself.
3. **The Sky reveal (projector):** stars fade in one society at a time, then lines
   draw, then the guessed-vs-actual stats count up.

---

## 5. Sound (optional polish)

Meta publishes a free **Sound Kit for prototypes** (interaction sounds) and rights-cleared
music at https://design.facebook.com/tools/. Good uses: a soft chime when a society forms,
a short sound on match confirm. Keep sounds off by default on phones; on for the
projector view.

---

## 6. Styling system choice

- facebook.com is styled with **StyleX**, Meta's open-source styling system
  (https://stylexjs.com). Using it is a nice detail for Meta judges.
- **But:** the deadline is tight. If the repo already uses Tailwind or plain CSS, stay
  with it and implement the tokens above as CSS variables. Do not migrate styling
  systems mid-build.

---

## 7. Layout notes

- **Phones (players):** single column, max-width 480px, bottom-anchored primary
  action, large tap targets (min 44px).
- **Projector (the Sky):** full-screen dark sky, large type (stats at 48px+), high
  contrast, no small text. Test from the back of a room.
- **Operator console:** dense, functional, light theme. Clarity over beauty.
- Add `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`
  and pad for safe areas on phones.

---

## 8. Accessibility checklist

- Text contrast at least 4.5:1 (the tokens above meet this on their backgrounds).
- All animations respect `prefers-reduced-motion`.
- Buttons have visible focus states (2px `--fb-blue-ui` outline).
- Voice input always has a text fallback (per PRD F2).
- Don't rely on color alone: confirmed vs pending states also differ in icon or label.
