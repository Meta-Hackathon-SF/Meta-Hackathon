import { expect, test } from "@playwright/test";

test("home renders 44 posts (14 + 30 demo population) with local images and no runtime errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 400)
      errors.push(`${response.status()} ${response.url()}`);
  });
  await page.goto("/");
  await expect(page.getByRole("main", { name: "News Feed" })).toBeVisible();
  await expect(page.locator(".feed-posts > article")).toHaveCount(44);
  await expect(
    page.getByRole("region", { name: "Stories", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("#post-hackathon .post-images img"),
  ).toHaveJSProperty("complete", true);
  expect(
    await page
      .locator("#post-hackathon .post-images img")
      .evaluate((image: HTMLImageElement) => image.naturalWidth),
  ).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test("like and unlike survive a page refresh", async ({ page }) => {
  await page.goto("/");
  const post = page.locator("#post-hackathon");
  const like = post.getByRole("button", { name: "Like", exact: true });
  await like.click();
  await expect(like).toHaveAttribute("aria-pressed", "true");
  await expect(post.locator(".reaction-count")).toHaveText("129");
  await page.reload();
  await expect(like).toHaveAttribute("aria-pressed", "true");
  await like.click();
  await expect(like).toHaveAttribute("aria-pressed", "false");
  await expect(post.locator(".reaction-count")).toHaveText("128");
});

test("create a post, validate empty input, and persist it", async ({
  page,
}) => {
  await page.goto("/");
  await page.locator(".composer-prompt").click();
  const dialog = page.getByRole("dialog", { name: "Create post" });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Post", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByRole("textbox", { name: "Post text" })
    .fill("Building a closer campus together! Test post.");
  await dialog.getByRole("button", { name: "Post", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".feed-posts > article").first()).toContainText(
    "Building a closer campus together! Test post.",
  );
  await expect(page.locator(".feed-posts > article")).toHaveCount(45);
  await page.reload();
  await expect(page.locator(".feed-posts > article").first()).toContainText(
    "Building a closer campus together! Test post.",
  );
});

test("comments, long text, and saved posts work", async ({ page }) => {
  await page.goto("/");
  const post = page.locator("#post-hackathon");
  await post.getByRole("button", { name: "Comment", exact: true }).click();
  await post
    .getByRole("textbox", { name: "Write a comment" })
    .fill("See you at the hackathon!");
  await post.getByRole("button", { name: "Send comment" }).click();
  await expect(post.locator(".comment-bubble")).toContainText(
    "See you at the hackathon!",
  );
  await expect(post.getByRole("button", { name: "25 comments" })).toBeVisible();
  await post.getByRole("button", { name: "Post options" }).click();
  await post.getByRole("button", { name: "Save post", exact: true }).click();
  await page.goto("/saved");
  await expect(page.locator("#post-hackathon")).toBeVisible();
  await page.goto("/?post=ai-builders");
  const expand = page
    .locator("#post-ai-builders")
    .getByRole("button", { name: "See more", exact: true });
  await expand.click();
  await expect(
    page
      .locator("#post-ai-builders")
      .getByRole("button", { name: "See less", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".post-text")).toContainText(
    "drop a resource that helped you get started",
  );
});

test("navigation and every secondary route support direct visits", async ({
  page,
  isMobile,
}) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", {
    name: isMobile ? "Mobile navigation" : "Main navigation",
    exact: true,
  });
  await nav.getByRole("link", { name: "Friends", exact: true }).click();
  await expect(page).toHaveURL("/friends");
  await expect(
    page.getByRole("heading", { name: "Friends", exact: true }),
  ).toBeVisible();
  for (const [route, title] of Object.entries({
    groups: "Groups",
    marketplace: "Marketplace",
    watch: "Reels",
    events: "Events",
    saved: "Saved",
    memories: "Memories",
    profile: "Your profile",
    messages: "Messenger",
    notifications: "Notifications",
  })) {
    const response = await page.goto(`/${route}`);
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: title, exact: true, level: 1 }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});

test("search and header menus work", async ({ page, isMobile }) => {
  await page.goto("/");
  if (isMobile) {
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page
      .getByRole("textbox", { name: "Search demo posts" })
      .fill("study session");
    await page
      .getByRole("textbox", { name: "Search demo posts" })
      .press("Enter");
  } else {
    await page
      .getByRole("textbox", { name: "Search Facebook" })
      .fill("study session");
    await page.getByRole("textbox", { name: "Search Facebook" }).press("Enter");
  }
  await expect(page).toHaveURL(/q=study%20session/);
  await expect(page.locator("#post-study-group")).toBeVisible();
  await page.getByRole("button", { name: "Messenger", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Messenger", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("region", { name: "Messenger", exact: true }),
  ).not.toBeVisible();
  if (isMobile) {
    await page.getByRole("button", { name: "Open menu" }).click();
    await page
      .getByRole("region", { name: "Menu", exact: true })
      .getByRole("link", { name: "Memories", exact: true })
      .click();
    await expect(page).toHaveURL("/memories");
  } else {
    await page.getByRole("button", { name: "Account", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "Account menu" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Notifications", exact: true })
      .click();
    await page.getByRole("button", { name: "Mark all as read" }).click();
    await expect(
      page.locator(".header-controls .notification-badge:visible"),
    ).toHaveCount(0);
  }
});

test("responsive widths have no overflow and correct navigation", async ({
  page,
}) => {
  await page.goto("/");
  for (const width of [375, 390, 428, 768]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("main", { name: "News Feed" })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    if (width < 768) {
      await expect(
        page.getByRole("navigation", { name: "Mobile navigation" }),
      ).toBeVisible();
      await expect(
        page.getByRole("complementary", { name: "Shortcuts" }),
      ).not.toBeVisible();
    }
  }
});

test("stories, photo previews, sharing, and dialog keyboard behavior work", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "View Maya Chen's story" }).click();
  await expect(
    page.getByRole("dialog", { name: "Maya Chen's story" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const post = page.locator("#post-hackathon");
  await post.getByRole("button", { name: /Open photo 1/ }).click();
  await expect(
    page.getByRole("dialog", { name: "Photo", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await post.getByRole("button", { name: "Share", exact: true }).click();
  await page.getByRole("button", { name: "Share now", exact: true }).click();
  await expect(post.locator(".post-stats")).toContainText("9 shares");
  await page.locator(".composer-prompt").click();
  await page.locator("input[type=file]").setInputFiles("public/demo/cat.jpg");
  await expect(page.locator(".attachment-previews img")).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Post", exact: true })
    .click();
  await expect(
    page.locator(".feed-posts > article").first().locator(".post-images img"),
  ).toBeVisible();
});
