import { expect, test } from "@playwright/test";

const preview = "/src/features/constellations/chat/test-only/index.html";
test.beforeEach(async ({ page }) => {
  await page.goto(preview);
});

test("shared fixtures are anonymous, labeled and never show removed messages", async ({
  page,
}, info) => {
  await expect(
    page.getByRole("heading", { name: "A little less alone" }),
  ).toBeVisible();
  await expect(page.getByText("Simulated Facebook")).toBeVisible();
  await expect(page.getByText("text me at 555-0100")).toHaveCount(0);
  await expect(
    page.getByText("Synthetic player A", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("complementary", { name: "Synthetic signals" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("constellations-preview.png"),
    fullPage: true,
  });
});

test("send works and contact information is rejected without a message bubble", async ({
  page,
}) => {
  const input = page.getByLabel("Message your constellation");
  await input.fill("A synthetic hello");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByText("A synthetic hello", { exact: true }),
  ).toBeVisible();
  await input.fill("call 555-0100");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Message not sent");
  await expect(page.locator(".cst-messages")).not.toContainText(
    "call 555-0100",
  );
});

test("report hides immediately and one-sided reveal has no identity", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Report Star 2 message" }).click();
  await expect(page.getByText("ok this is weirdly comforting")).toHaveCount(0);
  await page.getByRole("button", { name: "Reveal with Star 2" }).click();
  await expect(
    page.getByText("Identity stays private until you both choose to reveal."),
  ).toBeVisible();
  await expect(page.locator(".cst-mutual")).toHaveCount(0);
  await page.getByText("Test-only controls", { exact: true }).click();
  await page.getByRole("button", { name: "Simulate mutual consent" }).click();
  await expect(page.locator(".cst-mutual")).toContainText("Synthetic player A");
});

test("expired room is read-only and below-threshold labels/headlines never render", async ({
  page,
}) => {
  await page.getByText("Test-only controls", { exact: true }).click();
  await page.getByRole("button", { name: "Simulate room expiry" }).click();
  await expect(page.getByLabel("Message your constellation")).toBeDisabled();
  await expect(
    page.getByText("Room expired | Messages are read-only"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add suppressed theme" }).click();
  await expect(page.getByText("SYNTHETIC BELOW THRESHOLD")).toHaveCount(0);
});

test("cancel and room change discard a delayed response", async ({ page }) => {
  const input = page.getByLabel("Message your constellation");
  await input.fill("SYNTHETIC STALE RESPONSE");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Cancel pending action" }).click();
  await page.getByText("Test-only controls", { exact: true }).click();
  await page.getByRole("button", { name: "Switch fixture room" }).click();
  await expect(input).toBeEmpty();
  await expect(page.locator("html")).toHaveAttribute(
    "data-synthetic-response-count",
    "1",
  );
  await expect(page.locator(".cst-messages")).not.toContainText(
    "SYNTHETIC STALE RESPONSE",
  );
});
