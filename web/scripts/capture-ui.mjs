import { chromium } from "@playwright/test";
import fs from "node:fs/promises";

const round = process.argv[2] || "latest";
if (!/^[a-zA-Z0-9_-]+$/.test(round))
  throw new Error("Use a simple directory name for the capture round.");
const directory = `artifacts/visual/${round}`;
await fs.mkdir(directory, { recursive: true });
const browser = await chromium.launch({
  channel:
    process.env.PLAYWRIGHT_CHANNEL ||
    (process.platform === "win32" ? "chrome" : undefined),
});
const metrics = [];
try {
  for (const [name, width, height] of [
    ["desktop", 1440, 900],
    ["laptop", 1280, 800],
    ["tablet", 768, 1024],
    ["mobile", 390, 844],
    ["small-mobile", 375, 812],
  ]) {
    const page = await browser.newPage({
      viewport: { width, height },
      deviceScaleFactor: 1,
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    await page.goto(process.env.PREVIEW_URL || "http://127.0.0.1:5173", {
      waitUntil: "networkidle",
    });
    await page.locator(".post-card").first().waitFor();
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        Array.from(document.images)
          .filter((image) => image.loading !== "lazy")
          .map((image) =>
            image.complete
              ? Promise.resolve()
              : new Promise((resolve) => {
                  image.onload = resolve;
                  image.onerror = resolve;
                }),
          ),
      );
    });
    await page.screenshot({
      path: `${directory}/${name}.png`,
      animations: "disabled",
    });
    await page
      .locator("#post-hackathon .post-actions")
      .scrollIntoViewIfNeeded();
    // Let Chromium paint sticky elements after the programmatic scroll.
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    await page.screenshot({
      path: `${directory}/${name}-post-actions.png`,
      animations: "disabled",
    });
    const layout = await page.evaluate(() => {
      const feed = document.querySelector(".feed").getBoundingClientRect();
      const images = [...document.images]
        .filter((image) => image.complete && image.naturalWidth === 0)
        .map((image) => image.src);
      return {
        feed: { x: feed.x, width: feed.width },
        overflow: document.documentElement.scrollWidth > innerWidth,
        brokenImages: images,
      };
    });
    metrics.push({ name, viewport: `${width}x${height}`, ...layout, errors });
    console.log(
      `${name}: ${width}x${height}, feed ${layout.feed.width}px at x=${layout.feed.x}, overflow=${layout.overflow}, errors=${errors.length}`,
    );
    await page.close();
  }
} finally {
  await browser.close();
}
await fs.writeFile(
  `${directory}/metrics.json`,
  JSON.stringify(metrics, null, 2),
);
if (
  metrics.some(
    (result) =>
      result.overflow || result.errors.length || result.brokenImages.length,
  )
)
  process.exitCode = 1;
