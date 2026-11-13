import { expect, test } from "@playwright/test";
import { createChatClient, ChatHttpError } from "../client";
import { parseStreamEvent } from "../streamRuntime";

const message = {
  messageId: "synthetic-message",
  roomId: "synthetic-room",
  handle: "Star 1",
  text: "Synthetic message",
  createdAt: "2026-11-16T18:00:00Z",
  moderation: "visible",
  kind: "player",
};
const frame = (seq: number, id = seq) =>
  `id: ${id}\r\nevent: chat.message\r\ndata: ${JSON.stringify({ type: "chat.message", seq, message })}\r\n\r\n`;

function streamed(chunks: string[]) {
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks)
          controller.enqueue(new TextEncoder().encode(chunk));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream; charset=utf-8" } },
  );
}

test("SSE parser handles split chunks and replay header without duplicate delivery", async () => {
  const controller = new AbortController();
  const events: number[] = [];
  const requests: RequestInit[] = [];
  const client = createChatClient({
    fetcher: (async (_input, init) => {
      requests.push(init!);
      if (requests.length === 1) {
        const value = frame(1);
        return streamed([
          value.slice(0, 11),
          value.slice(11, 39),
          value.slice(39),
        ]);
      }
      return streamed([frame(1), frame(2)]);
    }) as typeof fetch,
  });
  await client.stream({
    signal: controller.signal,
    onEvent(event) {
      events.push(event.seq);
      if (event.seq === 2) controller.abort();
    },
  });
  expect(events).toEqual([1, 2]);
  expect(requests[0].credentials).toBe("include");
  expect(new Headers(requests[1].headers).get("Last-Event-ID")).toBe("1");
});

test("mismatched event ID is rejected without advancing the replay cursor", async () => {
  const controller = new AbortController();
  const events: number[] = [];
  const requests: RequestInit[] = [];
  const client = createChatClient({
    fetcher: (async (_input, init) => {
      requests.push(init!);
      return streamed([requests.length === 1 ? frame(1, 9) : frame(2)]);
    }) as typeof fetch,
  });
  await client.stream({
    signal: controller.signal,
    onEvent(event) {
      events.push(event.seq);
      controller.abort();
    },
  });
  expect(events).toEqual([2]);
  expect(new Headers(requests[1].headers).has("Last-Event-ID")).toBe(false);
});

test("private fields and nonfinite sequence numbers fail runtime validation", () => {
  expect(() =>
    parseStreamEvent({
      type: "chat.message",
      seq: 1,
      message: { ...message, playerId: "private" },
    }),
  ).toThrow();
  expect(() =>
    parseStreamEvent({ type: "chat.message", seq: NaN, message }),
  ).toThrow();
  expect(() =>
    parseStreamEvent({
      type: "chat.message",
      seq: Number.MAX_SAFE_INTEGER + 1,
      message,
    }),
  ).toThrow();
  expect(() =>
    parseStreamEvent({
      type: "chat.moderated",
      seq: 1,
      messageId: "synthetic",
      moderation: "visible",
      answer: "private",
    }),
  ).toThrow();
});

test("HTTP errors expose only the stable code and never server detail text", async () => {
  const client = createChatClient({
    fetcher: (async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "MESSAGE_REJECTED",
            message: "SYNTHETIC PRIVATE ERROR BODY",
            requestId: "synthetic",
            retryable: false,
          },
        }),
        { status: 422 },
      )) as typeof fetch,
  });
  try {
    await client.actions("synthetic-room").send("hello", {
      key: "synthetic-key",
      signal: new AbortController().signal,
    });
    throw new Error("expected rejection");
  } catch (error) {
    expect(error).toBeInstanceOf(ChatHttpError);
    expect((error as ChatHttpError).code).toBe("MESSAGE_REJECTED");
    expect((error as Error).message).not.toContain(
      "SYNTHETIC PRIVATE ERROR BODY",
    );
  }
});

test("malformed unauthorized response still fails closed from its HTTP status", async () => {
  const client = createChatClient({
    fetcher: (async () =>
      new Response("synthetic non-JSON auth body", {
        status: 401,
      })) as typeof fetch,
  });
  try {
    await client.getRoom("synthetic-cycle", new AbortController().signal);
    throw new Error("expected rejection");
  } catch (error) {
    expect(error).toBeInstanceOf(ChatHttpError);
    expect((error as ChatHttpError).code).toBe("UNAUTHENTICATED");
  }
});

test("a room from another requested cycle is rejected before display", async () => {
  const client = createChatClient({
    fetcher: (async () =>
      new Response(
        JSON.stringify({
          roomId: "synthetic-room",
          constellationId: "synthetic-c",
          cycleId: "other-cycle",
          status: "open",
          opensAt: "2026-11-15T18:00:00Z",
          expiresAt: "2026-11-21T20:00:00Z",
          members: [],
        }),
      )) as typeof fetch,
  });
  await expect(
    client.getRoom("synthetic-cycle", new AbortController().signal),
  ).rejects.toBeInstanceOf(ChatHttpError);
});

test("only the exact private support rejection variant sets the local support marker", async () => {
  const exact = "This message was held. A private support card is available.";
  for (const [status, code, message, expected] of [
    [422, "MESSAGE_REJECTED", exact, true],
    [422, "MESSAGE_REJECTED", "This message cannot be shared.", false],
    [422, "MESSAGE_REJECTED", `${exact} Unexpected extra text`, false],
    [422, "INVALID_INPUT", exact, false],
    [503, "MESSAGE_REJECTED", exact, false],
  ] as const) {
    const client = createChatClient({
      fetcher: (async () =>
        new Response(
          JSON.stringify({
            error: {
              code,
              message,
              requestId: "synthetic-request",
              retryable: false,
            },
          }),
          { status },
        )) as typeof fetch,
    });
    try {
      await client
        .actions("synthetic-room")
        .send("Synthetic message", {
          key: "synthetic-support-key",
          signal: new AbortController().signal,
        });
      throw new Error("expected rejection");
    } catch (error) {
      expect(error).toBeInstanceOf(ChatHttpError);
      expect((error as ChatHttpError).supportAvailable).toBe(expected);
      expect((error as Error).message).toBe(
        "The chat service could not complete this request.",
      );
    }
  }
});
