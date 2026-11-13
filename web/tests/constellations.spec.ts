import { expect, test, type Page } from "@playwright/test";

/*
 * Constellations daily loop + operator console (Will).
 * Runs against the in-browser FIXTURE adapter only: no server, no Muse, no
 * speech-to-text. These tests prove UI behavior, not live integration.
 */
const DAILY = "/groups/hackathon-builders/constellations";
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

async function answer(page: Page, day: number, text: string) {
  const card = page.getByTestId(`cst-day-${day}`);
  await card.getByRole("textbox", { name: "Your answer" }).fill(text);
  await card.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByTestId(`cst-answer-text-${day}`)).toHaveText(text);
}

test("Groups links to the Constellations tab with truth labels", async ({ page }) => {
  await page.goto("/groups");
  await page.getByRole("link", { name: "Constellations" }).click();
  await expect(page).toHaveURL(new RegExp(`${DAILY}$`));
  await expect(page.getByRole("heading", { level: 1, name: "Constellations" })).toBeVisible();
  await expect(page.getByText("Simulated Facebook", { exact: true })).toBeVisible();
  await expect(page.getByTestId("cst-mode")).toHaveText(/Fixture mode/);
  await expect(page.getByRole("heading", { name: "No week is running yet" })).toBeVisible();
  await page.goto("/groups/not-a-group/constellations");
  await expect(page.getByRole("heading", { name: "Group not found" })).toBeVisible();
});

test("typed answer, one follow-up, edit and delete, by keyboard", async ({ page }) => {
  await newCycle(page);
  await page.goto(DAILY);
  await expect(page.getByText("Demo timing", { exact: true })).toBeVisible();
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 0/);
  const card = page.getByTestId("cst-day-1");
  await expect(card.getByRole("button", { name: "Submit answer" })).toBeDisabled();
  await card.getByRole("textbox", { name: "Your answer" }).fill("alone mostly");
  await page.keyboard.press("Tab"); // record button
  await page.keyboard.press("Tab"); // submit
  await page.keyboard.press("Enter");
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
  await expect(page.getByTestId("cst-day-1").getByRole("textbox", { name: "Your answer" })).toBeVisible();
  await expect(page.getByTestId("cst-streak")).toHaveText(/Streak 0/);
});

test("microphone denied: typing still submits", async ({ page }) => {
  await fakeMicrophone(page, "deny");
  await newCycle(page);
  await page.goto(DAILY);
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
  await page.goto(DAILY);
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
  await page.goto(DAILY);
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
  await page.goto(DAILY);
  const slider = page.getByRole("slider", { name: /Your guess/ });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await page.getByRole("button", { name: "Save guess" }).click();
  await expect(page.getByText("Saved: 51%")).toBeVisible();
  await answer(page, 1, "SYNTHETIC SAFETY TEST: marker text");
  await expect(page.getByTestId("cst-support-card")).toContainText("988");
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
  await page.goto(DAILY);
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
