/// <reference types="node" />
import { expect, test } from "@playwright/test";
import type { Page, Route } from "@playwright/test";
import { readFileSync } from "node:fs";

const chat = JSON.parse(
  readFileSync(
    new URL(
      "../../../../../../contracts/fixtures/chat-room.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const skyFixture = JSON.parse(
  readFileSync(
    new URL(
      "../../../../../../contracts/fixtures/sky-stats.json",
      import.meta.url,
    ),
    "utf8",
  ),
).sky;
const playerMessage = { ...chat.messages[1], text: "Synthetic HTTP hello" };
const sse = (event: object & { seq: number; type: string }) =>
  `id: ${event.seq}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
const error = (code: string) => ({
  error: {
    code,
    message: "SYNTHETIC SERVER DETAIL MUST NOT RENDER",
    requestId: "synthetic-request",
    retryable: false,
  },
});

type Harness = {
  requests: {
    path: string;
    method: string;
    body: unknown;
    key?: string;
    after?: string;
  }[];
  streamCalls: number;
  events: (call: number) => object[];
  messages: object[];
  onRoom?: (route: Route, cycle: string) => Promise<void>;
};
async function setup(page: Page) {
  await page.clock.install({ time: new Date("2026-11-16T18:00:00Z") });
  const state: Harness = {
    requests: [],
    streamCalls: 0,
    events: () => [],
    messages: [playerMessage],
  };
  await page.route("**/test-api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/test-api", "");
    let body: unknown;
    if (request.postData()) body = request.postDataJSON();
    state.requests.push({
      path,
      method: request.method(),
      body,
      key: request.headers()["idempotency-key"],
      after: request.headers()["last-event-id"],
    });
    if (path === "/stream") {
      const events = state.events(++state.streamCalls);
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: events
          .map((event) => sse(event as { seq: number; type: string }))
          .join(""),
      });
      return;
    }
    if (/^\/cycles\/[^/]+\/room$/.test(path)) {
      const cycle = path.split("/")[2];
      if (state.onRoom) {
        await state.onRoom(route, cycle);
        return;
      }
      await route.fulfill({ json: { ...chat.room, cycleId: cycle } });
      return;
    }
    if (/^\/cycles\/[^/]+\/sky$/.test(path)) {
      await route.fulfill({
        json: { ...skyFixture, cycleId: path.split("/")[2], evidence: [] },
      });
      return;
    }
    if (path.endsWith("/messages") && request.method() === "GET") {
      await route.fulfill({ json: state.messages });
      return;
    }
    if (path.endsWith("/messages") && request.method() === "POST") {
      await route.fulfill({
        json: {
          ...playerMessage,
          messageId: "synthetic-sent",
          handle: "Star 1",
          text: (body as { text: string }).text,
        },
      });
      return;
    }
    if (path.endsWith("/reports")) {
      state.messages = [];
      await route.fulfill({ status: 204 });
      return;
    }
    if (path === "/me/blocks") {
      state.messages = [];
      await route.fulfill({ status: 204 });
      return;
    }
    if (path.endsWith("/reveal")) {
      await route.fulfill({ json: { result: "pending" } });
      return;
    }
    await route.fulfill({ status: 404, json: error("NOT_FOUND") });
  });
  return state;
}
const live = "/src/features/constellations/chat/test-only/live.html";

test("real HTTP adapter sends scoped bodies and keys; pending reveal has no identity", async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto(live);
  await expect(
    page.getByText("Synthetic HTTP hello", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Message your constellation")
    .fill("Synthetic sent text");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByText("Synthetic sent text", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reveal with Star 2" }).click();
  await expect(page.locator(".cst-mutual")).toHaveCount(0);
  await page.getByRole("button", { name: "Report Star 2 message" }).click();
  await expect(
    page.getByText("Synthetic HTTP hello", { exact: true }),
  ).toHaveCount(0);
  const writes = state.requests.filter((request) => request.method === "POST");
  expect(writes.length).toBe(3);
  expect(writes.every((request) => !!request.key)).toBe(true);
  expect(writes.map((request) => request.body)).toEqual([
    { text: "Synthetic sent text" },
    { toHandle: "Star 2" },
    { messageId: playerMessage.messageId, handle: "Star 2", reason: "other" },
  ]);
  expect(JSON.stringify(writes)).not.toContain("playerId");
});

test("SSE reconnect carries sequence, deduplicates replay and hides moderation", async ({
  page,
}) => {
  const state = await setup(page);
  state.events = (call) =>
    call === 1
      ? [{ type: "chat.message", seq: 1, message: playerMessage }]
      : call === 2
        ? [
            { type: "chat.message", seq: 1, message: playerMessage },
            {
              type: "chat.moderated",
              seq: 2,
              messageId: playerMessage.messageId,
              moderation: "hidden_pending",
            },
          ]
        : [];
  await page.goto(live);
  await expect.poll(() => state.streamCalls).toBeGreaterThanOrEqual(2);
  await expect(
    page.getByText("Synthetic HTTP hello", { exact: true }),
  ).toHaveCount(0);
  expect(
    state.requests.filter((request) => request.path === "/stream")[1].after,
  ).toBe("1");
});

test("foreign-room identities and chat never render; exact room expiry disables writes", async ({
  page,
}) => {
  const state = await setup(page);
  state.events = (call) =>
    call === 1
      ? [
          {
            type: "chat.message",
            seq: 1,
            message: {
              ...playerMessage,
              roomId: "foreign-room",
              text: "SYNTHETIC FOREIGN TEXT",
            },
          },
          {
            type: "reveal.mutual",
            seq: 2,
            reveal: {
              roomId: "foreign-room",
              players: [
                {
                  playerId: "synthetic-a",
                  displayName: "SYNTHETIC FOREIGN IDENTITY",
                  avatarColor: "#7c9cff",
                  isSynthetic: true,
                },
                {
                  playerId: "synthetic-b",
                  displayName: "Synthetic B",
                  avatarColor: "#7c9cff",
                  isSynthetic: true,
                },
              ],
              revealedAt: "2026-11-16T18:00:00Z",
            },
          },
          { type: "room.expired", seq: 3, roomId: chat.room.roomId },
        ]
      : [];
  await page.goto(live);
  await expect(
    page.getByText("Room expired | Messages are read-only"),
  ).toBeVisible();
  await expect(page.getByLabel("Message your constellation")).toBeDisabled();
  await expect(page.getByText("SYNTHETIC FOREIGN TEXT")).toHaveCount(0);
  await expect(page.getByText("SYNTHETIC FOREIGN IDENTITY")).toHaveCount(0);
});

test("authorization loss clears the current room instead of retaining identities", async ({
  page,
}) => {
  const state = await setup(page);
  state.events = () => [];
  await page.goto(live);
  await expect(
    page.getByText("Synthetic HTTP hello", { exact: true }),
  ).toBeVisible();
  await page.route("**/test-api/stream", (route) =>
    route.fulfill({ status: 401, json: error("UNAUTHENTICATED") }),
  );
  await expect(
    page.getByText(
      "Your verified session needs attention. Rejoin or restore consent to continue.",
    ),
  ).toBeVisible();
  await expect(page.locator(".cst-chat")).toHaveCount(0);
  await expect(
    page.getByText("SYNTHETIC SERVER DETAIL MUST NOT RENDER"),
  ).toHaveCount(0);
});

test("switching cycles aborts and ignores an older room response", async ({
  page,
}) => {
  const state = await setup(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let oldStarted = false;
  let oldSettled = false;
  state.onRoom = async (route, cycle) => {
    if (cycle === "cycle-demo-w1") {
      oldStarted = true;
      await gate;
      try {
        await route.fulfill({
          json: {
            ...chat.room,
            members: chat.room.members.map((member: { handle: string }) => ({
              ...member,
              handle:
                member.handle === "Star 2"
                  ? "SYNTHETIC STALE MEMBER"
                  : member.handle,
            })),
          },
        });
      } catch {
        /* canceled route */
      }
      oldSettled = true;
    } else await route.fulfill({ json: { ...chat.room, cycleId: cycle } });
  };
  await page.goto(live);
  await expect.poll(() => oldStarted).toBe(true);
  await page.getByRole("button", { name: "Switch test cycle" }).click();
  await expect(
    page.getByText("Synthetic HTTP hello", { exact: true }),
  ).toBeVisible();
  release();
  await expect.poll(() => oldSettled).toBe(true);
  await expect(page.getByText("SYNTHETIC STALE MEMBER")).toHaveCount(0);
});

test("a delayed pre-expiry snapshot cannot reopen an expired room", async ({
  page,
}) => {
  const state = await setup(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let reads = 0;
  let settled = false;
  state.onRoom = async (route) => {
    const read = ++reads;
    if (read > 1) {
      await gate;
      state.messages = [
        {
          ...playerMessage,
          messageId: "synthetic-refreshed",
          text: "Synthetic refreshed snapshot",
        },
      ];
    }
    await route.fulfill({ json: chat.room });
    if (read > 1) settled = true;
  };
  state.events = (call) =>
    call === 1
      ? [
          {
            type: "chat.moderated",
            seq: 1,
            messageId: playerMessage.messageId,
            moderation: "hidden_pending",
          },
          { type: "room.expired", seq: 2, roomId: chat.room.roomId },
        ]
      : [];
  await page.goto(live);
  await expect(
    page.getByText("Room expired | Messages are read-only"),
  ).toBeVisible();
  await expect.poll(() => reads).toBeGreaterThan(1);
  release();
  await expect.poll(() => settled).toBe(true);
  await expect(
    page.getByText("Synthetic refreshed snapshot", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Message your constellation")).toBeDisabled();
  await expect(
    page.getByText("Room expired | Messages are read-only"),
  ).toBeVisible();
});

test("mutual identities require the current viewer even inside the same room", async ({
  page,
}) => {
  const state = await setup(page);
  const player = (playerId: string, displayName: string) => ({
    playerId,
    displayName,
    avatarColor: "#7c9cff",
    isSynthetic: true,
  });
  state.events = (call) =>
    call === 1
      ? [
          {
            type: "reveal.mutual",
            seq: 1,
            reveal: {
              roomId: chat.room.roomId,
              players: [
                player("foreign-a", "SYNTHETIC WRONG PAIR"),
                player("foreign-b", "Synthetic foreign"),
              ],
              revealedAt: "2026-11-16T18:00:00Z",
            },
          },
          {
            type: "reveal.mutual",
            seq: 2,
            reveal: {
              roomId: chat.room.roomId,
              players: [
                player("synthetic-a", "Synthetic viewer"),
                player("synthetic-b", "Synthetic partner"),
              ],
              revealedAt: "2026-11-16T18:00:00Z",
            },
          },
        ]
      : [];
  await page.goto(live);
  await expect(page.locator(".cst-mutual")).toContainText("Synthetic viewer");
  await expect(page.getByText("SYNTHETIC WRONG PAIR")).toHaveCount(0);
});
