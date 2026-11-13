import { expect, test, type Page } from "@playwright/test";

/*
 * Facebook Space tab (V4 design) + operator console (Will).
 * Runs against the in-browser FIXTURE adapter only: no server, no Muse, no
 * speech-to-text. These tests prove UI behavior, not live integration.
 */
const DAILY = "/space";
const OPERATOR = `${DAILY}/operator`;
const LONG = "Mostly the dining hall with my floor, loud but good";

async function fakeMicrophone(page: Page, behavior: "allow" | "deny") {
  await page.addInitScript((mode) => {
    // Force the recorder path: the demo-only browser speech engine would bypass the fixture transcript.
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "webkitSpeechRecognition", { configurable: true, value: undefined });
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
    await page.locator(".cst-op-advance").click();
    await expect(page.getByTestId("cst-op-state")).not.toHaveText(before ?? "");
  }
}

/** Join screen (fixture privacy client): Select all, then Join this week. */
async function join(page: Page) {
  await expect(page.getByTestId("cstp-join")).toBeVisible();
  await page.getByTestId("spc-join-all").click();
  await page.getByTestId("cstp-join-submit").click();
  await expect(page.getByTestId("cstp-join")).toHaveCount(0);
}

/** Open the Space tab, joining first if this tab has no session yet. */
async function openSpace(page: Page) {
  await page.goto(DAILY);
  const joinForm = page.getByTestId("cstp-join");
  const home = page.getByTestId("spc-home").or(page.getByText("No week is running yet"));
  await expect(joinForm.or(home).first()).toBeVisible();
  if (await joinForm.isVisible()) await join(page);
  await expect(page.getByRole("heading", { level: 1, name: /Space/ })).toBeVisible();
}

/** Answer a day on its answer screen; resolves on the next screen (sky, follow-up or support). */
async function answer(page: Page, day: number, text: string) {
  await page.goto(`${DAILY}?s=answer&day=${day}`);
  await page.getByRole("textbox", { name: "Your answer" }).fill(text);
  await page.getByRole("button", { name: /^(Submit|Save changes)$/ }).click();
  await expect(page).toHaveURL(/s=(daily|followup|distress)/);
}

test("Space tab: truth labels, join is gated by the required consents, old links redirect", async ({ page }) => {
  await page.goto("/groups/hackathon-builders/constellations");
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  const joinForm = page.getByTestId("cstp-join");
  await expect(joinForm.getByRole("heading", { name: "Before you play" })).toBeVisible();
  await expect(page.getByTestId("cstp-join-submit")).toBeDisabled();
  await page.getByTestId("cstp-toggle-matchAnswers").click();
  await page.getByTestId("cstp-toggle-anonymousChat").click();
  await expect(page.getByTestId("cstp-join-submit")).toBeDisabled(); // age is required
  await page.getByTestId("cstp-toggle-isAdult").click();
  await expect(page.getByTestId("cstp-join-submit")).toBeEnabled();
  await page.getByTestId("cstp-join-submit").click();
  await expect(page.getByRole("heading", { name: "No week is running yet" })).toBeVisible();
  await expect(page.getByTestId("cst-mode")).toHaveText(/Fixture mode/);
  await page.goto("/constellations");
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await page.goto("/groups/any-group/constellations/operator");
  await expect(page).toHaveURL(new RegExp(`${OPERATOR}$`));
});

test("today's question: post privately from Space home, see today's sky, edit later", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await expect(page.getByText("Demo timing", { exact: true }).first()).toBeVisible();
  const today = page.getByTestId("spc-today");
  await expect(today).toContainText("Where did you eat most of your meals");
  await expect(today.getByRole("button", { name: "Post privately" })).toBeDisabled();
  await today.getByRole("textbox", { name: "Your answer" }).fill(LONG);
  await today.getByRole("button", { name: "Post privately" }).click();
  await expect(page).toHaveURL(/s=daily&day=1/);
  const stage = page.getByTestId("spc-canvas-daily");
  await expect(stage.getByText("Monday", { exact: true })).toBeVisible();
  await expect(stage.getByText(/^\d[\d,]* people answered today$/)).toBeAttached();
  await expect(stage).not.toContainText(LONG); // your words never show on the sky
  await stage.getByRole("button", { name: "Done" }).click();
  await expect(page.getByTestId("spc-week-1").getByRole("button", { name: "Monday: Answered" })).toBeVisible();
  await expect(today).toContainText("You answered today");
  await today.getByRole("button", { name: "Edit" }).click();
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(LONG);
  await page.getByRole("textbox", { name: "Your answer" }).fill("edited answer text");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page).toHaveURL(/s=daily/);
});

test("one follow-up, labeled fixture; a reply that would not fit is blocked, never cut", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, "alone mostly");
  await expect(page).toHaveURL(/s=followup/);
  await expect(page.getByTestId("cst-muse-chip")).toHaveText(/Fixture follow-up · not Muse/);
  const box = page.getByRole("textbox", { name: "What made it feel that way this week?" });
  await box.fill("x".repeat(400));
  await expect(box).toHaveValue("x".repeat(400)); // nothing trimmed
  await expect(page.getByTestId("spc-fu-count")).toHaveClass(/spc-count-over/);
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await box.fill("by choice, I think");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page).toHaveURL(/s=daily&day=1/);
  await page.goto(`${DAILY}?s=answer&day=1`);
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue("alone mostly by choice, I think");
});

test("microphone denied: typing still submits", async ({ page }) => {
  await fakeMicrophone(page, "deny");
  await newCycle(page);
  await openSpace(page);
  const today = page.getByTestId("spc-today");
  await today.getByRole("button", { name: "Answer by voice" }).click();
  await expect(today.getByText("Mic is off. Typing works the same.")).toBeVisible();
  await expect(today.getByRole("button", { name: "Answer by voice" })).toBeDisabled();
  await today.getByRole("textbox", { name: "Your answer" }).fill(LONG);
  await today.getByRole("button", { name: "Post privately" }).click();
  await expect(page).toHaveURL(/s=daily/);
});

test("voice answer shows a labeled fixture transcript before anything is sent", async ({ page }) => {
  await fakeMicrophone(page, "allow");
  await newCycle(page);
  await openSpace(page);
  const today = page.getByTestId("spc-today");
  await today.getByRole("button", { name: "Answer by voice" }).click();
  await today.getByRole("button", { name: "Stop recording" }).click();
  await expect(today.getByText("Fixture transcript, not your voice. Edit it before posting.")).toBeVisible();
  await expect(today.getByRole("textbox", { name: "Your answer" })).toHaveValue(/^Synthetic transcript/);
  await expect(page.getByTestId("spc-week-1").getByRole("button")).toHaveCount(0); // nothing sent yet
});

test("streak: Mon and Tue on the day -> 2-day streak; a missed Wednesday shows in Catch up", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, LONG);
  await advance(page, 1);
  await answer(page, 2, LONG);
  await page.goto(DAILY);
  await expect(page.getByTestId("spc-today")).toContainText("2-day streak");
  await advance(page, 2); // Wednesday, then Wednesday ends
  await page.goto(DAILY);
  await expect(page.getByTestId("spc-today")).not.toContainText("streak");
  await expect(page.getByTestId("spc-catchup-3")).toHaveAccessibleName("Catch up: Wednesday's question");
  await expect(page.getByTestId("spc-week-5").getByRole("button")).toHaveCount(0); // future days not answerable
  await page.getByTestId("spc-catchup-3").click();
  await expect(page.getByRole("heading", { name: "Catch up · Wednesday" })).toBeVisible();
  await page.getByRole("textbox", { name: "Your answer" }).fill(LONG);
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page).toHaveURL(/s=daily&day=3/);
  await page.goto(DAILY);
  await expect(page.getByTestId("spc-catchup-3")).toHaveCount(0);
  await expect(page.getByTestId("spc-week-3").getByRole("button", { name: "Wednesday: Caught up" })).toBeVisible();
  await expect(page.getByTestId("spc-today")).toContainText("2-day streak"); // catch-up never extends it
});

test("no prevalence guess (D012); a flagged answer shows the private support card", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await expect(page.getByRole("slider")).toHaveCount(0);
  await answer(page, 1, "SYNTHETIC SAFETY TEST: marker text");
  await expect(page).toHaveURL(/s=distress/);
  const support = page.getByTestId("spc-support");
  await expect(support).toContainText("won't be used in the game");
  await expect(support.getByRole("link", { name: "Call" })).toHaveAttribute("href", "tel:988");
  await expect(page.getByTestId("cst-muse-chip")).toHaveCount(0); // flagged text gets no follow-up
});

test("weekend: lock closes answers, week sky and formation are labeled previews, reveal opens chat", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, LONG);
  await advance(page, 5); // Tue..Fri, then lock
  await page.goto(DAILY);
  await expect(page.getByTestId("spc-weekend-sat")).toContainText("Your week is in the sky");
  await expect(page.locator("#main-content").getByRole("textbox")).toHaveCount(0);
  await page.getByRole("button", { name: "View sky" }).click();
  const sky = page.getByTestId("spc-canvas-sky");
  await expect(sky.getByText(/answers this week/)).toBeVisible();
  await sky.getByRole("button", { name: "Find my people" }).click();
  await expect(page.getByTestId("spc-canvas-forming").getByRole("status")).toHaveText(/Following one path|Ready/);
  await page.goto(`${DAILY}?s=main`);
  await expect(page.getByText("Not revealed yet")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open chat" })).toHaveCount(0);
  await advance(page, 2); // forming, revealed
  await page.goto(DAILY);
  await expect(page.getByTestId("spc-weekend-sun")).toContainText("Your constellation is ready");
  await page.getByRole("button", { name: "View constellation" }).click();
  await page.getByRole("button", { name: "Open chat" }).click();
  const chat = page.getByTestId("spc-chat");
  await expect(chat.getByText("Preview", { exact: true })).toBeVisible();
  await chat.getByRole("textbox", { name: "Message" }).fill("text me 765 555 0142");
  await chat.getByRole("button", { name: "Send", exact: true }).click();
  await expect(chat.getByRole("alert")).toContainText("couldn't be sent");
  await expect(chat.getByText("765 555 0142")).toHaveCount(0); // never posted, stays in the box only
  await chat.getByRole("button", { name: "Star 3" }).click();
  await expect(page.getByRole("dialog", { name: "Star 3" }).getByText("Names only show if you both ask.")).toBeVisible();
});

test("privacy: turning matching off shows it on Sunday; delete my data returns to Join", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, LONG);
  await page.goto(`${DAILY}?s=settings`);
  const match = page.getByTestId("spc-set-match");
  await expect(match).toHaveAttribute("aria-checked", "true");
  await match.click();
  await expect(match).toHaveAttribute("aria-checked", "false");
  await page.goto(`${DAILY}?s=main`);
  await expect(page.getByText("Matching is off")).toBeVisible();
  await page.goto(`${DAILY}?s=settings`);
  await page.getByRole("button", { name: "Delete all my data" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByTestId("cstp-join")).toBeVisible();
});

test("Space has no horizontal overflow on a small phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, LONG);
  for (const path of [DAILY, `${DAILY}?s=settings`, `${DAILY}?s=events`, OPERATOR]) {
    await page.goto(path);
    await page.waitForTimeout(200);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});

test("home feed: Facebook Space sits under the composer and answers without leaving Home", async ({ page, isMobile }) => {
  await page.goto("/");
  const feed = page.getByRole("main", { name: "News Feed" });
  const card = feed.getByTestId("cst-feed-card");
  await expect(card).toBeVisible();
  const order = await feed.evaluate((main) =>
    [...main.children]
      .filter((el) => !el.classList.contains("sr-only"))
      .map((el) => el.getAttribute("aria-label") ?? el.className)
      .slice(0, 2),
  );
  expect(order[0]).toBe("Create a post");
  expect(order[1]).toBe("Facebook Space");
  await card.getByRole("link", { name: "Join", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await join(page);
  await newCycle(page);
  await page.goto("/");
  await expect(card).toContainText("Where did you eat most of your meals");
  await expect(card).toContainText("Monday's question · Private");
  await card.getByRole("textbox", { name: "Your answer" }).fill(LONG);
  await page.keyboard.press("Enter"); // like posting a comment
  await expect(card.getByText(LONG)).toBeVisible(); // your own private comment
  await expect(card).toContainText("Only you");
  await expect(card.getByTestId("cst-feed-streak")).toHaveText(/1-day streak/);
  await expect(card).toContainText(/answered today/);
  await expect(card.getByRole("link", { name: "See today's stars" })).toHaveCount(0);
  await card.getByRole("link", { name: "Open Space" }).click();
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await page.goto(`${DAILY}?s=answer&day=1`);
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue(LONG); // one source of truth
  if (!isMobile) {
    const explore = page.getByRole("navigation", { name: "Explore" });
    await expect(explore.getByRole("link", { name: "Facebook Space" })).toHaveClass(/active/);
    await expect(explore.getByRole("link", { name: "Groups" })).not.toHaveClass(/active/);
  }
});

test("operator runs a full demo week in under 3 minutes; lock closes answers", async ({ page }) => {
  const started = Date.now();
  await newCycle(page);
  await expect(page.getByText("Demo timing", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Synthetic top-up" }).click();
  await expect(page.getByTestId("cst-op-status")).toHaveText(/Synthetic player top-up: 8 synthetic players/);
  await expect(page.getByText("None. Fixture mode never calls Muse.").first()).toBeVisible();
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
  await openSpace(page);
  await expect(page.getByTestId("spc-weekend-sat")).toBeVisible();
  await expect(page.locator("#main-content").getByRole("textbox")).toHaveCount(0);
  await page.goto(OPERATOR);
  for (const [button, state] of [
    ["Start formation", "Forming"],
    ["Reveal constellations (Sunday 10:00)", "Revealed"],
    ["Close the week", "Closed"],
  ]) {
    await page.getByRole("button", { name: button }).click();
    await expect(page.getByTestId("cst-op-state")).toHaveText(state);
  }
  await expect(page.locator(".cst-op-advance")).toHaveCount(0); // nothing after closed
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

test("operator posts an event nudge to the revealed room (fixture replay, approved venue)", async ({ page }) => {
  await newCycle(page);
  await openSpace(page); // the operator also plays, so they have a room after reveal
  await page.goto(OPERATOR);
  const nudge = page.getByTestId("cst-op-nudge");
  await expect(nudge).toContainText("open after Sunday's reveal");
  await advance(page, 7); // Tue..Fri, lock, form, reveal
  await expect(page.getByTestId("cst-op-state")).toContainText(/Reveal/i);
  await expect(nudge.getByRole("combobox", { name: "Room" })).toHaveValue("room-orion");
  await nudge.getByRole("button", { name: "Post event nudge" }).click();
  await expect(nudge).toContainText("Replay of a saved cycle");
  await expect(nudge).toContainText("Campus Cafe");
  await expect(nudge).toContainText("Fixture mode");
});

test("v3 operator: custom-event proposals are approved or rejected and the decision is logged", async ({ page }) => {
  await newCycle(page);
  const queue = page.getByTestId("cst-op-custom-events");
  await expect(queue.locator(".cst-proposal")).toHaveCount(2);
  await expect(queue.getByText("Replay of a saved round").first()).toBeVisible();
  await expect(queue.getByText(/muse-spark-1\.3 · M7/).first()).toBeVisible();
  await queue.locator(".cst-proposal").first().getByRole("button", { name: "Approve" }).click();
  await expect(queue.locator(".cst-proposal")).toHaveCount(1);
  await queue.locator(".cst-proposal").first().getByRole("textbox").fill("Venue too far");
  await queue.locator(".cst-proposal").first().getByRole("button", { name: "Reject" }).click();
  await expect(queue.getByText("No proposals waiting.")).toBeVisible();
  const log = page.getByTestId("cst-op-decision-log");
  await expect(log.locator("li")).toHaveCount(2);
  await expect(log).toContainText("Approved “Saturday dumpling night”");
  await expect(log).toContainText("Rejected “Sunday morning walk and coffee”");
});

test("operator reasoning panel: Muse proposes, code enforces (fixture shows none)", async ({ page }) => {
  await newCycle(page);
  const panel = page.getByTestId("cst-op-reasoning");
  await expect(panel.getByRole("heading", { name: "Muse proposes, code enforces" })).toBeVisible();
  await expect(panel.getByText("None. Fixture mode never calls Muse.")).toBeVisible();
});

async function toSundayChat(page: Page) {
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, LONG);
  await advance(page, 7); // Tue..Fri, lock, forming, revealed
  await page.goto(`${DAILY}?s=main`);
  await page.getByRole("button", { name: "Open chat" }).click();
  return page.getByTestId("spc-chat");
}

test("v3 sky: entering the sky plays the telescope zoom; Sunday draws the Meta logo ribbon", async ({ page }) => {
  await newCycle(page);
  await openSpace(page);
  await answer(page, 1, LONG);
  await advance(page, 5);
  await page.goto(DAILY);
  await page.getByRole("button", { name: "View sky" }).click();
  await expect(page.getByTestId("spc-telescope")).toBeVisible(); // iris + streaks on entry
  await expect(page.getByTestId("spc-telescope")).toHaveCount(0, { timeout: 5000 }); // removes itself
  await advance(page, 2);
  await page.goto(`${DAILY}?s=main`);
  await expect(page.getByTestId("spc-canvas-main")).toBeVisible();
});

test("v3 chat: minimise to the dock, reopen, and a room not everyone kept disappears", async ({ page }) => {
  const chat = await toSundayChat(page);
  await chat.getByRole("button", { name: "Minimise chat" }).click();
  const dock = page.getByTestId("spc-chat-dock");
  await expect(dock).toBeVisible();
  await page.evaluate(() => { window.history.pushState({}, "", "/messages"); window.dispatchEvent(new PopStateEvent("popstate")); });
  await expect(dock).toBeVisible(); // follows the player around the shell
  await expect(page.getByTestId("messenger-constellation")).toHaveCount(0); // not kept: not in Messenger
  await dock.click();
  await expect(page.getByTestId("spc-chat")).toBeVisible();
  await page.getByTestId("spc-chat-expire").click(); // demo: run out the 24 h without everyone keeping
  await expect(page.getByTestId("spc-chat-expired")).toContainText("This room has closed");
  await page.evaluate(() => { window.history.pushState({}, "", "/messages"); window.dispatchEvent(new PopStateEvent("popstate")); });
  await expect(page.getByTestId("messenger-constellation")).toHaveCount(0);
  await expect(page.getByTestId("spc-chat-dock")).toHaveCount(0);
});

// No live source for other members' keep votes yet; re-enable when the chat route delivers them.
test.fixme("v3 chat: if everyone keeps it, it moves into Messenger", async ({ page }) => {
  const chat = await toSundayChat(page);
  await chat.getByRole("button", { name: "Keep", exact: true }).click(); // the others follow
  await expect(page.getByTestId("spc-send-messenger")).toBeVisible({ timeout: 6000 }); // fold + fly animation
  await expect(page.getByTestId("spc-send-messenger")).toHaveCount(0, { timeout: 6000 });
  await expect(chat.getByText("Everyone kept it. It moved to Messenger.")).toBeVisible();
  await chat.getByTestId("spc-open-messenger").click();
  await expect(page).toHaveURL(/\/messages/);
  await expect(page.getByTestId("messenger-constellation-thread")).toContainText("Your constellation");
  await expect(page.getByTestId("messenger-constellation-thread")).toContainText("same. tuesday's question got me");
});
