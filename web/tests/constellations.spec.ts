import { expect, test, type Page } from "@playwright/test";

/*
 * Constellations daily loop + operator console (Will).
 * Runs against the in-browser FIXTURE adapter only: no server, no Muse, no
 * speech-to-text. These tests prove UI behavior, not live integration.
 */
const DAILY = "/space";
const OPERATOR = `${DAILY}/operator`;
const LONG = "Mostly the dining hall with my floor, loud but good";

async function fakeMicrophone(page: Page, behavior: "allow" | "deny") {
  await page.addInitScript((mode) => {
    const stream = { getTracks: () => [{ stop() {} }] };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: () =>
          mode === "deny"
            ? Promise.reject(new DOMException("Permission denied", "NotAllowedError"))
            : Promise.resolve(stream),
      },
    });
    class FakeRecorder {
      state = "inactive";
      mimeType = "audio/webm";
      ondataavailable: ((e: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      static isTypeSupported = (t: string) => t.startsWith("audio/webm");
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob(["fake-audio"], { type: "audio/webm" }) });
        this.onstop?.();
      }
    }
    (window as unknown as { MediaRecorder: unknown }).MediaRecorder = FakeRecorder;
  }, behavior);
}

async function newCycle(page: Page) {
  await page.goto(OPERATOR);
  await page.getByRole("button", { name: "New cycle" }).click();
  await expect(page.getByTestId("cst-op-state")).toHaveText("Open · Monday");
}

async function advance(page: Page, times: number) {
  await page.goto(OPERATOR);
  for (let i = 0; i < times; i++) {
    const before = await page.getByTestId("cst-op-state").textContent();
    await page.locator(".button-primary").click();
    await expect(page.getByTestId("cst-op-state")).not.toHaveText(before ?? "");
  }
}

/** Patrik's join screen (fixture privacy client): name + all three consents. */
async function join(page: Page, name = "Synthetic tester") {
  await expect(page.getByTestId("cstp-join")).toBeVisible();
  await page.getByTestId("cstp-name").fill(name);
  for (const key of ["matchAnswers", "anonymousChat", "isAdult"]) await page.getByTestId(`cstp-toggle-${key}`).click();
  await page.getByTestId("cstp-join-submit").click();
  await expect(page.getByTestId("cstp-join")).toHaveCount(0);
}

/** Open the daily page, joining first if this tab has no session yet. */
async function openDaily(page: Page) {
  await page.goto(DAILY);
  const joinForm = page.getByTestId("cstp-join");
  const ready = page.locator(".cst-week, .cst-empty");
  await expect(joinForm.or(ready).first()).toBeVisible();
  if (await joinForm.isVisible()) await join(page);
}

async function answer(page: Page, day: number, text: string) {
  const card = page.getByTestId(`cst-day-${day}`);
  await card.getByRole("textbox", { name: "Your answer" }).fill(text);
  await card.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByTestId(`cst-answer-text-${day}`)).toHaveText(text);
}

test("Constellations is a Facebook-wide page with truth labels; old Group links redirect", async ({ page }) => {
  await page.goto("/groups/hackathon-builders/constellations");
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await expect(page.getByRole("heading", { level: 1, name: "Facebook Space" })).toBeVisible();
  await expect(page.getByText("Simulated Facebook", { exact: true })).toBeVisible();
  await expect(page.getByTestId("cst-mode")).toHaveText(/Fixture mode/);
  // Nothing about the week loads before joining with all three consents.
  await expect(page.getByTestId("cstp-join-submit")).toBeDisabled();
  await expect(page.locator(".cst-week, .cst-empty")).toHaveCount(0);
  await join(page);
  await expect(page.getByRole("heading", { name: "No week is running yet" })).toBeVisible();
  await expect(page.getByTestId("cstp-panel")).toBeVisible();
  await page.goto("/constellations");
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await page.goto("/groups/any-group/constellations/operator");
  await expect(page).toHaveURL(new RegExp(`${OPERATOR}$`));
});

test("Constellation tab explains the idea with a labeled example; there is no separate Sky", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  const tabs = page.getByRole("tablist", { name: "Facebook Space sections" });
  await expect(tabs.getByRole("tab")).toHaveCount(2);
  await expect(tabs.getByRole("tab", { name: /Sky/ })).toHaveCount(0);
  await expect(tabs.getByRole("tab", { name: "This week" })).toHaveAttribute("aria-selected", "true");
  await tabs.getByRole("tab", { name: /Constellation/ }).click();
  await expect(tabs.getByRole("tab", { name: /Constellation/ })).toHaveAttribute("aria-selected", "true");
  const panel = page.getByRole("tabpanel");
  await expect(panel.getByRole("heading", { name: "Your constellation" })).toBeVisible();
  // Every card on this tab is an Example until formation and the reveal view supply real data.
  await expect(panel.getByText("Example", { exact: true })).toHaveCount(3);
  await expect(panel.getByRole("img", { name: /closer people shine brighter/ })).toBeVisible();
  await tabs.getByRole("tab", { name: "This week" }).click();
  await expect(page.getByTestId("cst-day-1")).toBeVisible();
});

test("why-this-group shows counts only, and new data sources need the player's OK", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  await page.getByRole("tab", { name: /Constellation/ }).click();
  const why = page.getByTestId("cst-why");
  await expect(why.getByRole("heading", { name: "Why this group" })).toBeVisible();
  await expect(why.getByText("Example", { exact: true })).toBeVisible();
  await expect(why).toContainText("2 of your 4 stars");
  await expect(why).toContainText("after you both choose to reveal");
  // No Star handle is tied to a shared Group, friend or event before reveal.
  await expect(why).not.toContainText(/Star \d/);
  for (const source of ["Groups you're in", "Events you're going to", "Posts and comments"]) {
    await expect(why.getByRole("listitem").filter({ hasText: source })).toContainText("Needs your OK");
  }
  await expect(why.getByRole("listitem").filter({ hasText: "Daily answers" })).toContainText("On");
});

test("event heat hides events under 3 similar people and buckets the rest", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  await page.getByRole("tab", { name: /Constellation/ }).click();
  const heat = page.getByTestId("cst-heat");
  await expect(heat.getByText("Example", { exact: true })).toBeVisible();
  const rows = heat.getByTestId("cst-heat-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.first()).toContainText("Board game night");
  await expect(rows.first()).toContainText("10+ people like you");
  await expect(heat).not.toContainText("Film club"); // 2 similar people: below threshold
  await expect(heat).not.toContainText(/\b(11|6) people/); // exact counts never shown
  const interested = rows.first().getByRole("button", { name: "Interested" });
  await interested.click();
  await expect(interested).toHaveAttribute("aria-pressed", "true");
});

test("streak rewards come from on-day answers; catch-ups count for every-day but not perfect week", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  const rewards = page.getByTestId("cst-rewards");
  await expect(rewards).toContainText("0 of 4 earned");
  await expect(rewards).toContainText("Next: First light");
  await answer(page, 1, "Board games with my floor");
  await expect(page.getByTestId("cst-reward-first-light")).toHaveClass(/is-earned/);
  await expect(rewards).toContainText("1 of 4 earned");
  await advance(page, 1);
  await openDaily(page);
  await answer(page, 2, "Walking to class with music");
  await advance(page, 1);
  await openDaily(page);
  await answer(page, 3, "Cooking with my roommate");
  await expect(page.getByTestId("cst-reward-three-in-a-row")).toHaveClass(/is-earned/);
  await expect(page.getByTestId("cst-reward-perfect-week")).not.toHaveClass(/is-earned/);
  await expect(rewards).toContainText("never change who you're matched with");
});

test("answer box grows with text and never shows a scrollbar for normal answers", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  const box = page.getByTestId("cst-day-1").getByRole("textbox", { name: "Your answer" });
  await box.fill("one line");
  const one = await box.evaluate((el) => ({ h: el.clientHeight, sh: el.scrollHeight, o: getComputedStyle(el).overflowY }));
  expect(one.o).toBe("hidden");
  expect(one.sh).toBeLessThanOrEqual(one.h + 1);
  await box.fill("line\n".repeat(4) + "last line");
  const five = await box.evaluate((el) => ({ h: el.clientHeight, sh: el.scrollHeight, o: getComputedStyle(el).overflowY }));
  expect(five.h).toBeGreaterThan(one.h);
  expect(five.o).toBe("hidden");
  expect(five.sh).toBeLessThanOrEqual(five.h + 1);
});

test("typed answer, one follow-up, edit and delete, by keyboard", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  await expect(page.getByText("Demo timing", { exact: true })).toBeVisible();
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 0/);
  const card = page.getByTestId("cst-day-1");
  await expect(card.getByRole("button", { name: "Submit answer" })).toBeDisabled();
  await card.getByRole("textbox", { name: "Your answer" }).fill("alone mostly");
  await page.keyboard.press("Enter"); // Enter sends, like a Facebook comment
  await expect(page.getByTestId("cst-answer-text-1")).toHaveText("alone mostly");
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 1/);
  await expect(page.getByTestId("cst-muse-chip")).toHaveText(/Fixture follow-up · not Muse/);
  await card.getByRole("textbox", { name: "What made it feel that way this week?" }).fill("by choice, I think");
  await card.getByRole("button", { name: "Add to my answer" }).click();
  await expect(page.getByTestId("cst-answer-text-1")).toHaveText("alone mostly by choice, I think");
  await expect(page.getByTestId("cst-muse-chip")).toHaveCount(0); // one follow-up max
  await card.getByRole("button", { name: "Edit" }).click();
  await card.getByRole("textbox", { name: "Edit your answer" }).fill("edited answer text");
  await card.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByTestId("cst-answer-text-1")).toHaveText("edited answer text");
  await page.reload();
  await expect(page.getByTestId("cst-answer-text-1")).toHaveText("edited answer text");
  await page.getByTestId("cst-day-1").getByRole("button", { name: "Delete" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete answer?" });
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId("cst-answer-text-1")).toBeVisible(); // nothing deleted until confirmed
  await dialog.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByTestId("cst-day-1").getByRole("textbox", { name: "Your answer" })).toBeVisible();
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 0/);
});

test("microphone denied: typing still submits", async ({ page }) => {
  await fakeMicrophone(page, "deny");
  await newCycle(page);
  await openDaily(page);
  const card = page.getByTestId("cst-day-1");
  await card.getByRole("button", { name: "Record answer" }).click();
  await expect(card.getByText("Microphone access is off. Typing works the same.")).toBeVisible();
  await expect(card.getByRole("button", { name: "Record answer" })).toBeDisabled();
  await answer(page, 1, LONG);
  await expect(card.getByText(/private to you · typed/)).toBeVisible();
});

test("voice answer shows a labeled fixture transcript before submit", async ({ page }) => {
  await fakeMicrophone(page, "allow");
  await newCycle(page);
  await openDaily(page);
  const card = page.getByTestId("cst-day-1");
  await card.getByRole("button", { name: "Record answer" }).click();
  await card.getByRole("button", { name: /^Stop/ }).click();
  await expect(card.getByText("Fixture transcript, not your voice. Edit it before submitting.")).toBeVisible();
  await expect(card.getByRole("textbox", { name: "Your answer" })).toHaveValue(/^Synthetic transcript/);
  await expect(page.getByTestId("cst-answer-text-1")).toHaveCount(0); // nothing sent until submit
  await card.getByRole("button", { name: "Submit answer" }).click();
  await expect(card.getByText(/private to you · from voice/)).toBeVisible();
});

test("streak fixture: Mon and Tue on the day, Wed caught up -> streak 2", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  await answer(page, 1, LONG);
  await advance(page, 1);
  await page.goto(DAILY);
  await answer(page, 2, LONG);
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 2/);
  await advance(page, 2); // Wednesday, then Wednesday ends
  await page.goto(DAILY);
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 0/);
  await expect(page.getByTestId("cst-catchup-note")).toHaveText(/1 missed day to catch up/);
  await expect(page.getByTestId("cst-day-3").getByText("Catch-up · Wednesday")).toBeVisible();
  await expect(page.getByTestId("cst-day-5")).toHaveCount(0); // future days never shown
  await answer(page, 3, LONG);
  await expect(page.getByTestId("cst-day-3").getByText(/Saved as catch-up/)).toBeVisible();
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 2/);
  await expect(page.getByTestId("cst-catchup-note")).toHaveCount(0);
});

test("guess slider saves, and a flagged answer shows the private support card", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  const slider = page.getByRole("slider", { name: /Your guess/ });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await page.getByRole("button", { name: "Save guess" }).click();
  await expect(page.getByText("Saved: 51%")).toBeVisible();
  await answer(page, 1, "SYNTHETIC SAFETY TEST: marker text");
  await expect(page.getByTestId("cstp-support-card")).toContainText("988");
  await expect(page.getByTestId("cstp-support-card").getByRole("link", { name: "988" })).toHaveAttribute("href", "tel:988");
  await expect(page.getByTestId("cst-muse-chip")).toHaveCount(0); // flagged text gets no follow-up
});

test("operator runs a full demo week in under 3 minutes; lock closes answers", async ({ page }) => {
  const started = Date.now();
  await newCycle(page);
  await expect(page.getByText("Demo timing", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Synthetic top-up" }).click();
  await expect(page.getByTestId("cst-op-status")).toHaveText(/Synthetic player top-up: 8 synthetic players/);
  await expect(page.getByText("None. Fixture mode never calls Muse.")).toBeVisible();
  for (const [button, state] of [
    ["Advance to Tuesday", "Open · Tuesday"],
    ["Advance to Wednesday", "Open · Wednesday"],
    ["Advance to Thursday", "Open · Thursday"],
    ["Advance to Friday", "Open · Friday"],
    ["Lock the week (Saturday 12:00)", "Locked"],
  ]) {
    await page.getByRole("button", { name: button }).click();
    await expect(page.getByTestId("cst-op-state")).toHaveText(state);
  }
  await expect(page.getByRole("button", { name: "Synthetic top-up" })).toBeDisabled();
  await openDaily(page);
  await expect(page.getByTestId("cst-locked")).toContainText("This week is locked");
  await expect(page.locator(".cst-page").getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("slider")).toHaveCount(0);
  await page.goto(OPERATOR);
  for (const [button, state] of [
    ["Start formation", "Forming"],
    ["Reveal constellations (Sunday 10:00)", "Revealed"],
    ["Close the week", "Closed"],
  ]) {
    await page.getByRole("button", { name: button }).click();
    await expect(page.getByTestId("cst-op-state")).toHaveText(state);
  }
  await expect(page.locator(".button-primary")).toHaveCount(0); // nothing after closed
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.getByTestId("cst-op-state")).toHaveText("Closed"); // nothing changes until confirmed
  await page.getByRole("button", { name: "Reset week" }).click();
  await expect(page.getByTestId("cst-op-state")).toHaveText("Open · Monday");
  expect(Date.now() - started).toBeLessThan(180_000);
});

test("recordings are converted to 16 kHz mono 16-bit WAV before upload", async ({ page }) => {
  await page.goto(DAILY);
  const result = await page.evaluate(async () => {
    const { encodeWav, toWav } = await import("/src/features/constellations/daily/wav.ts");
    // A synthetic one-second 440 Hz stereo-rate source at 48 kHz, as a phone might record.
    const source = new Float32Array(48000);
    for (let i = 0; i < source.length; i++) source[i] = 0.5 * Math.sin((2 * Math.PI * 440 * i) / 48000);
    const converted: Blob = await toWav(encodeWav(source, 48000));
    const view = new DataView(await converted.arrayBuffer());
    const tag = (o: number) => String.fromCharCode(...[0, 1, 2, 3].map((i) => view.getUint8(o + i)));
    let peak = 0;
    for (let o = 44; o < view.byteLength; o += 2) peak = Math.max(peak, Math.abs(view.getInt16(o, true)));
    return {
      type: converted.type,
      riff: tag(0),
      wave: tag(8),
      format: view.getUint16(20, true),
      channels: view.getUint16(22, true),
      rate: view.getUint32(24, true),
      bits: view.getUint16(34, true),
      samples: view.getUint32(40, true) / 2,
      peak,
    };
  });
  expect(result).toMatchObject({ type: "audio/wav", riff: "RIFF", wave: "WAVE", format: 1, channels: 1, rate: 16000, bits: 16 });
  expect(result.samples).toBeGreaterThan(15900);
  expect(result.samples).toBeLessThan(16100);
  expect(result.peak).toBeGreaterThan(12000); // the tone survived, not silence
  expect(result.peak).toBeLessThan(20000);
});

test("pausing consent hides the week; delete my data clears answers", async ({ page }) => {
  await newCycle(page);
  await openDaily(page);
  await answer(page, 1, LONG);
  await page.getByTestId("cstp-panel").locator("summary").click();
  await page.getByTestId("cstp-toggle-matchAnswers").click();
  await page.getByTestId("cstp-save").click();
  await expect(page.locator(".cst-week")).toHaveCount(0);
  await expect(page.getByTestId("cst-answer-text-1")).toHaveCount(0);
  await page.getByTestId("cstp-toggle-matchAnswers").click();
  await page.getByTestId("cstp-save").click();
  await expect(page.getByTestId("cst-answer-text-1")).toHaveText(LONG);
  await page.getByTestId("cstp-panel").locator("summary").click();
  await page.getByTestId("cstp-delete").click();
  await page.getByTestId("cstp-delete-confirm").click();
  await expect(page.getByTestId("cst-day-1").getByRole("textbox", { name: "Your answer" })).toBeVisible();
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 0/);
});

test("new cycle asks before replacing a running week", async ({ page }) => {
  await newCycle(page);
  await page.getByRole("button", { name: "Advance to Tuesday" }).click();
  await expect(page.getByTestId("cst-op-state")).toHaveText("Open · Tuesday");
  await page.getByRole("button", { name: "New cycle" }).click();
  await expect(page.getByRole("group", { name: "Confirm new week" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByTestId("cst-op-state")).toHaveText("Open · Tuesday");
  await page.getByRole("button", { name: "New cycle" }).click();
  await page.getByRole("button", { name: "Start new week" }).click();
  await expect(page.getByTestId("cst-op-state")).toHaveText("Open · Monday");
});

test("week view has no horizontal overflow on a small phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await newCycle(page);
  await openDaily(page);
  await answer(page, 1, LONG);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await page.goto(OPERATOR);
  const opOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(opOverflow).toBeLessThanOrEqual(0);
});

test("home feed: Constellations sits under the composer and works without leaving Home", async ({ page, isMobile }) => {
  await page.goto("/");
  const feed = page.getByRole("main", { name: "News Feed" });
  const card = feed.getByTestId("cst-feed-card");
  await expect(card).toBeVisible();
  // Directly after "What's on your mind?", before stories and posts.
  const order = await feed.evaluate((main) =>
    [...main.children]
      .filter((el) => !el.classList.contains("sr-only"))
      .map((el) => el.getAttribute("aria-label") ?? el.className)
      .slice(0, 2),
  );
  expect(order[0]).toBe("Create a post");
  expect(order[1]).toBe("Facebook Space");
  await card.getByRole("button", { name: "Join this week" }).click();
  await join(page, "Feed tester");
  await expect(card.getByText(/No week is running yet/)).toBeVisible();
  await newCycle(page);
  await page.goto("/");
  await expect(card.getByRole("heading", { name: /Where did you eat most of your meals/ })).toBeVisible();
  await card.getByRole("textbox", { name: "Your answer" }).fill(LONG);
  await page.keyboard.press("Enter");
  await expect(card.getByTestId("cst-answer-text-1")).toHaveText(LONG);
  await expect(card.getByTestId("cst-feed-streak")).toHaveText("1");
  await expect(card.getByTestId("cst-feed-next")).toBeAttached();
  await card.getByRole("link", { name: /See your week/ }).click();
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await expect(page.getByTestId("cst-answer-text-1")).toHaveText(LONG); // same answer, one source of truth
  if (!isMobile) {
    // Desktop sidebar: only the Constellations shortcut is highlighted, not Groups too.
    const explore = page.getByRole("navigation", { name: "Explore" });
    await expect(explore.getByRole("link", { name: "Facebook Space" })).toHaveClass(/active/);
    await expect(explore.getByRole("link", { name: "Groups" })).not.toHaveClass(/active/);
  }
});

test("week graph: day nodes are keyboard reachable and open their question", async ({ page }) => {
  await newCycle(page);
  await advance(page, 2); // Wednesday
  await openDaily(page);
  const graph = page.getByRole("group", { name: "Your week, one node per day" });
  await expect(graph).toBeVisible();
  const monday = graph.getByRole("button", { name: /^Monday: Catch up/ });
  await monday.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("cst-day-1").getByRole("textbox", { name: "Your answer" })).toBeFocused();
  await answer(page, 1, LONG);
  await expect(graph.getByRole("button", { name: /^Monday: Caught up/ })).toBeVisible();
  await expect(graph.getByRole("button", { name: /^Wednesday: Today/ })).toBeVisible();
});

test("Facebook-style shell: sidebar order, Meta AI and Gaming placeholders, new-message button", async ({ page, isMobile }) => {
  test.skip(isMobile, "desktop sidebar and floating button");
  await page.goto("/");
  const explore = page.getByRole("navigation", { name: "Explore" });
  const labels = (await explore.locator(".sidebar-row > span:last-child").allTextContents()).slice(1, 11);
  expect(labels).toEqual(["Meta AI", "Friends", "Memories", "Saved", "Groups", "Facebook Space", "Reels", "Marketplace", "Feeds", "Events"]);
  await expect(explore.getByRole("link", { name: "Feeds" })).not.toHaveClass(/active/);
  await expect(page.getByRole("region", { name: "Stories" }).getByRole("button", { name: /Create story/ })).toBeVisible();
  await page.getByRole("link", { name: "New message" }).click();
  await expect(page).toHaveURL("/messages");
  await expect(page.getByRole("link", { name: "New message" })).toHaveCount(0);
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Gaming" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Gaming" })).toBeVisible();
  await explore.getByRole("link", { name: "Meta AI" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Meta AI" })).toBeVisible();
  await page.getByRole("link", { name: "Open Facebook Space" }).click();
  await expect(page).toHaveURL(/\/space$/);
});
