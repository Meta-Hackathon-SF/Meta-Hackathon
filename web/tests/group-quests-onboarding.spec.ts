import { expect, test, type Page } from "@playwright/test";

/*
 * Group Quests onboarding (Will). Runs against the FIXTURE adapter only:
 * no Muse, STT or server is involved, and results prove local UI behavior,
 * not live integration.
 */
const ROUTE = "/groups/hackathon-builders/quests";

function tomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function grantFixtureConsent(page: Page) {
  await page.getByRole("checkbox", { name: /Fixture consent/ }).check();
}

/** Replace getUserMedia/MediaRecorder with deterministic fakes. */
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

test("Groups card links into Group Quests with visible demo labels", async ({ page }) => {
  await page.goto("/groups");
  await page.getByRole("link", { name: "Group Quests" }).first().click();
  await expect(page).toHaveURL(/\/groups\/hackathon-builders\/quests$/);
  await expect(page.getByRole("heading", { level: 1, name: "Group Quests" })).toBeVisible();
  await expect(page.getByText("Facebook integration simulated")).toBeVisible();
  await expect(page.getByTestId("gq-mode")).toHaveText(/Fixture mode/);
});

test("unknown community shows a not-found state", async ({ page }) => {
  await page.goto("/groups/not-a-community/quests");
  await expect(page.getByRole("heading", { name: "Community not found" })).toBeVisible();
});

test("nothing can be submitted before consent", async ({ page }) => {
  await page.goto(ROUTE);
  await expect(page.getByText("Turn on Group Quests consent above to continue.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Or type it" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Record voice note" })).toBeDisabled();
});

test("typed intent -> missing questions -> corrected fields -> confirmed, by keyboard", async ({
  page,
}) => {
  await page.goto(ROUTE);
  await grantFixtureConsent(page);
  const transcript = page.getByRole("textbox", { name: "Or type it" });
  await transcript.focus();
  await page.keyboard.type("A short photo walk near the main quad, under $10, about an hour.");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Continue" })).toBeFocused();
  await page.keyboard.press("Enter");

  const heading = page.getByRole("heading", { name: "Confirm your details" });
  await expect(heading).toBeFocused();
  // Fixture never guesses availability; it must be asked explicitly.
  await expect(page.getByRole("link", { name: /When are you free/ })).toBeVisible();
  await expect(page.getByText("Suggestions came from fixture keyword rules, not Muse.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: /Max budget per person/ })).toHaveValue("10");
  await expect(page.getByRole("combobox", { name: "Area" })).toHaveValue("main-quad");

  // Confirming with availability missing is blocked and focuses the field.
  await page.getByRole("button", { name: "Confirm intent" }).click();
  await expect(page.getByText("Add at least one time you're free.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add a time" })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByLabel("Date", { exact: true }).fill(tomorrow());
  await page.getByLabel("From", { exact: true }).fill("14:00");
  await page.getByLabel("To", { exact: true }).fill("16:00");

  // Correction: change budget and add an interest; the submission must reflect it.
  const budget = page.getByRole("textbox", { name: /Max budget per person/ });
  await budget.fill("5");
  const interest = page.getByRole("textbox", { name: "Interests" });
  await interest.fill("sketching");
  await interest.press("Enter");
  await page.getByRole("button", { name: "Remove walking" }).click();

  await page.getByRole("button", { name: "Confirm intent" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Intent confirmed" })).toBeFocused();
  const summary = page.getByTestId("gq-confirmed-summary");
  await expect(summary).toContainText("$5.00");
  await expect(summary).toContainText("photography, sketching");
  await expect(summary).not.toContainText("walking");
  await expect(summary).toContainText("Main Quad");
  await expect(page.getByText(/Version 1 · private to you · fixture save/)).toBeVisible();

  // Timer starts on confirmed intent and cannot complete without the events step.
  await expect(page.getByTestId("gq-timer-status")).toHaveText(/Can't stop yet/);

  // Editing a confirmed intent abandons the attempt and bumps the version on save.
  await page.getByRole("button", { name: "Edit intent" }).click();
  await expect(page.getByTestId("gq-timer-status")).toHaveText(/edited your intent/);
  await page.getByRole("combobox", { name: "Max time" }).selectOption("30");
  await page.getByRole("button", { name: "Confirm intent" }).click();
  await expect(page.getByText(/Version 2 · private to you/)).toBeVisible();
  await expect(page.getByTestId("gq-confirmed-summary")).toContainText("30 minutes");
});

test("cancelled extraction that returns late does not overwrite the transcript", async ({
  page,
}) => {
  await page.goto(`${ROUTE}?gqFixtureDelay=1500`);
  await grantFixtureConsent(page);
  const transcript = page.getByRole("textbox", { name: "Or type it" });
  await transcript.fill("Coffee near the student union, free.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Reading your intent" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await transcript.fill("Board games at the downtown library, $5, 90 minutes.");
  await page.waitForTimeout(2000); // past the cancelled request's delay
  await expect(page.getByRole("heading", { name: "Confirm your details" })).toHaveCount(0);
  await expect(transcript).toHaveValue("Board games at the downtown library, $5, 90 minutes.");

  // The current request still works and reflects the corrected text.
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Confirm your details" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove board games" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Area" })).toHaveValue("downtown-library");
});

test("provider failure shows a retryable error and keeps the typed text", async ({ page }) => {
  await page.goto(`${ROUTE}?gqFixtureFail=extract&gqFixtureDelay=0`);
  await grantFixtureConsent(page);
  const transcript = page.getByRole("textbox", { name: "Or type it" });
  await transcript.fill("Running club at the main quad.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("alert")).toContainText("The assistant is unavailable right now.");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(transcript).toHaveValue("Running club at the main quad.");
  // Manual path stays available when extraction is down.
  await page.getByRole("alert").getByRole("button", { name: "Fill in details myself" }).click();
  await expect(page.getByRole("heading", { name: "Confirm your details" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "What you'd enjoy" })).toHaveValue(
    "Running club at the main quad.",
  );
});

test("microphone denial explains the problem and keeps typing available", async ({ page }) => {
  await fakeMicrophone(page, "deny");
  await page.goto(ROUTE);
  await grantFixtureConsent(page);
  await page.getByRole("button", { name: "Record voice note" }).click();
  await expect(page.getByText(/Microphone access was blocked/)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Or type it" })).toBeEnabled();
});

test("unsupported browser hides recording and keeps typing available", async ({ page }) => {
  await page.addInitScript(() => {
    delete (window as unknown as { MediaRecorder?: unknown }).MediaRecorder;
  });
  await page.goto(ROUTE);
  await grantFixtureConsent(page);
  await expect(page.getByText(/Voice recording isn't available in this browser/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Record voice note" })).toBeDisabled();
  await expect(page.getByRole("textbox", { name: "Or type it" })).toBeEnabled();
});

test("voice note -> editable fixture transcript", async ({ page }) => {
  await fakeMicrophone(page, "allow");
  await page.goto(`${ROUTE}?gqFixtureDelay=0`);
  await grantFixtureConsent(page);
  await page.getByRole("button", { name: "Record voice note" }).click();
  await page.getByRole("button", { name: "Stop recording" }).click();
  const transcript = page.getByRole("textbox", { name: /Transcript/ });
  await expect(transcript).toHaveValue(/photo walk/);
  await expect(page.getByText(/Fixture transcript: your audio was not sent anywhere/)).toBeVisible();
  await transcript.fill("Photo walk at Engineering Plaza, free, 45 minutes.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("combobox", { name: "Area" })).toHaveValue("engineering-plaza");
  await expect(page.getByRole("textbox", { name: /Max budget per person/ })).toHaveValue("0");
});

test("feature page has no horizontal overflow", async ({ page }) => {
  await page.goto(ROUTE);
  await grantFixtureConsent(page);
  await page.getByRole("button", { name: "Fill in details myself" }).click();
  await page.getByRole("button", { name: "Add a time" }).click();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
