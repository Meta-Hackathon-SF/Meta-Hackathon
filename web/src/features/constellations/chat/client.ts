import type {
  ApiError,
  ChatMessage,
  ChatRoom,
  ErrorCode,
  SkyStats,
  StreamEvent,
} from "../../../../../contracts/protocol";
import type { ActionContext, ChatActions } from "./ChatPanel";
import {
  boolean,
  list,
  object,
  oneOf,
  parseMessage,
  parseRoom,
  text,
} from "./runtime";
import { parseSky } from "../sky/runtime";
import { parseStreamEvent } from "./streamRuntime";

const CODES: ErrorCode[] = [
  "INVALID_INPUT",
  "UNAUTHENTICATED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONSENT_REQUIRED",
  "STALE_REVISION",
  "PROVIDER_UNAVAILABLE",
  "RATE_LIMITED",
  "IDEMPOTENCY_CONFLICT",
  "CYCLE_LOCKED",
  "ROOM_EXPIRED",
  "MESSAGE_REJECTED",
];
export class ChatHttpError extends Error {
  code: ErrorCode;
  retryable: boolean;
  constructor(code: ErrorCode, retryable = false) {
    super("The chat service could not complete this request.");
    this.name = "ChatHttpError";
    this.code = code;
    this.retryable = retryable;
  }
}
export type StreamState = "connecting" | "connected" | "reconnecting";
export interface StreamOptions {
  signal: AbortSignal;
  after?: number;
  onEvent(event: StreamEvent): void | Promise<void>;
  onState?(state: StreamState): void;
}
export interface ChatClient {
  getRoom(cycleId: string, signal: AbortSignal): Promise<ChatRoom>;
  messages(
    roomId: string,
    after: number,
    signal: AbortSignal,
  ): Promise<ChatMessage[]>;
  sky(cycleId: string, signal: AbortSignal): Promise<SkyStats>;
  actions(roomId: string): ChatActions;
  stream(options: StreamOptions): Promise<void>;
}

async function responseError(response: Response): Promise<ChatHttpError> {
  const statusCode: ErrorCode =
    response.status === 401
      ? "UNAUTHENTICATED"
      : response.status === 403
        ? "FORBIDDEN"
        : response.status === 410
          ? "ROOM_EXPIRED"
          : response.status === 429
            ? "RATE_LIMITED"
            : "PROVIDER_UNAVAILABLE";
  try {
    const body = object(await response.json(), ["error"]);
    const detail = object(body.error, [
      "code",
      "message",
      "requestId",
      "retryable",
    ]);
    oneOf(detail.code, CODES);
    text(detail.message);
    text(detail.requestId);
    boolean(detail.retryable);
    const error = detail as unknown as ApiError["error"];
    return new ChatHttpError(
      response.status === 401 || response.status === 403
        ? statusCode
        : error.code,
      error.retryable,
    );
  } catch {
    return new ChatHttpError(
      statusCode,
      response.status >= 500 || response.status === 429,
    );
  }
}
function aborted(signal: AbortSignal) {
  if (signal.aborted) throw new DOMException("Request canceled", "AbortError");
}
async function wait(ms: number, signal: AbortSignal) {
  aborted(signal);
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(done, ms);
    function done() {
      signal.removeEventListener("abort", cancel);
      resolve();
    }
    function cancel() {
      clearTimeout(timer);
      reject(new DOMException("Request canceled", "AbortError"));
    }
    signal.addEventListener("abort", cancel, { once: true });
    if (signal.aborted) cancel();
  });
}

/** Session cookies are the identity. No playerId, fixture override or auth token is sent. */
export function createChatClient(
  options: { baseUrl?: string; fetcher?: typeof fetch } = {},
): ChatClient {
  const base = (options.baseUrl ?? "/api/v1").replace(/\/$/, "");
  const fetcher = options.fetcher ?? fetch;
  const path = (id: string) => encodeURIComponent(id);
  async function request(
    route: string,
    signal: AbortSignal,
    body?: unknown,
    key?: string,
  ): Promise<unknown> {
    aborted(signal);
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      headers["Idempotency-Key"] = key!;
    }
    const response = await fetcher(`${base}${route}`, {
      method: body === undefined ? "GET" : "POST",
      credentials: "include",
      signal,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    aborted(signal);
    if (!response.ok) throw await responseError(response);
    if (response.status === 204) return undefined;
    try {
      return await response.json();
    } catch {
      throw new ChatHttpError("PROVIDER_UNAVAILABLE", true);
    }
  }
  const mutate = (route: string, body: unknown, context: ActionContext) => {
    if (!/^[!-~]{1,128}$/.test(context.key))
      throw new ChatHttpError("INVALID_INPUT");
    return request(route, context.signal, body, context.key);
  };
  return {
    async getRoom(cycleId, signal) {
      const room = parseRoom(
        await request(`/cycles/${path(cycleId)}/room`, signal),
      );
      if (room.cycleId !== cycleId)
        throw new ChatHttpError("PROVIDER_UNAVAILABLE");
      return room;
    },
    async messages(roomId, after, signal) {
      if (!Number.isSafeInteger(after) || after < 0)
        throw new ChatHttpError("INVALID_INPUT");
      const result = await request(
        `/rooms/${path(roomId)}/messages?after=${after}`,
        signal,
      );
      list(result);
      return result.map(parseMessage).map((message) => {
        if (message.roomId !== roomId)
          throw new ChatHttpError("PROVIDER_UNAVAILABLE");
        return message;
      });
    },
    async sky(cycleId, signal) {
      const sky = parseSky(
        await request(`/cycles/${path(cycleId)}/sky`, signal),
      );
      if (sky.cycleId !== cycleId)
        throw new ChatHttpError("PROVIDER_UNAVAILABLE");
      return sky;
    },
    actions(roomId) {
      return {
        async send(text, context) {
          const message = parseMessage(
            await mutate(`/rooms/${path(roomId)}/messages`, { text }, context),
          );
          if (message.roomId !== roomId)
            throw new ChatHttpError("PROVIDER_UNAVAILABLE");
          return message;
        },
        async report(messageId, handle, reason, context) {
          await mutate(
            `/rooms/${path(roomId)}/reports`,
            { messageId, handle, reason },
            context,
          );
        },
        async block(handle, context) {
          await mutate("/me/blocks", { roomId, handle }, context);
        },
        async reveal(toHandle, context) {
          const result = object(
            await mutate(
              `/rooms/${path(roomId)}/reveal`,
              { toHandle },
              context,
            ),
            ["result"],
          );
          oneOf(result.result, ["pending", "revealed"]);
          return result;
        },
      };
    },
    async stream({ signal, after = 0, onEvent, onState }) {
      if (!Number.isSafeInteger(after) || after < 0)
        throw new ChatHttpError("INVALID_INPUT");
      let cursor = after;
      let delay = 500;
      let connecting = true;
      while (!signal.aborted) {
        onState?.(connecting ? "connecting" : "reconnecting");
        connecting = false;
        try {
          const headers: Record<string, string> = {
            Accept: "text/event-stream",
          };
          if (cursor > 0) headers["Last-Event-ID"] = String(cursor);
          const response = await fetcher(`${base}/stream`, {
            credentials: "include",
            signal,
            headers,
          });
          if (!response.ok) throw await responseError(response);
          if (
            !response.headers
              .get("Content-Type")
              ?.toLowerCase()
              .startsWith("text/event-stream") ||
            !response.body
          )
            throw new ChatHttpError("PROVIDER_UNAVAILABLE", true);
          onState?.("connected");
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let pending = "";
          let data: string[] = [];
          let id: string | undefined;
          let eventName: string | undefined;
          let frameSize = 0;
          async function dispatch() {
            if (data.length === 0) {
              id = undefined;
              eventName = undefined;
              frameSize = 0;
              return;
            }
            const event = parseStreamEvent(JSON.parse(data.join("\n")));
            if (
              id !== undefined &&
              (!/^[0-9]+$/.test(id) ||
                !Number.isSafeInteger(Number(id)) ||
                Number(id) !== event.seq)
            )
              throw new ChatHttpError("PROVIDER_UNAVAILABLE", true);
            if (eventName !== undefined && eventName !== event.type)
              throw new ChatHttpError("PROVIDER_UNAVAILABLE", true);
            if (!signal.aborted && event.seq > cursor) {
              await onEvent(event);
              cursor = event.seq;
              delay = 500;
            }
            data = [];
            id = undefined;
            eventName = undefined;
            frameSize = 0;
          }
          try {
            while (!signal.aborted) {
              const chunk = await reader.read();
              pending += decoder.decode(chunk.value, { stream: !chunk.done });
              let end: number;
              while ((end = pending.indexOf("\n")) !== -1) {
                const line = pending.slice(0, end).replace(/\r$/, "");
                pending = pending.slice(end + 1);
                if (line === "") await dispatch();
                else if (!line.startsWith(":")) {
                  frameSize += line.length + 1;
                  if (frameSize > 65536)
                    throw new ChatHttpError("PROVIDER_UNAVAILABLE", true);
                  const colon = line.indexOf(":");
                  const field = colon === -1 ? line : line.slice(0, colon);
                  const value =
                    colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
                  if (field === "data") data.push(value);
                  else if (field === "id") id = value;
                  else if (field === "event") eventName = value;
                }
              }
              if (pending.length > 65536)
                throw new ChatHttpError("PROVIDER_UNAVAILABLE", true);
              if (chunk.done) break;
            }
          } finally {
            await reader.cancel().catch(() => {});
            reader.releaseLock();
          }
        } catch (error) {
          if (signal.aborted) return;
          if (
            error instanceof ChatHttpError &&
            ["UNAUTHENTICATED", "FORBIDDEN", "CONSENT_REQUIRED"].includes(
              error.code,
            )
          )
            throw error;
        }
        if (!signal.aborted) {
          onState?.("reconnecting");
          await wait(delay, signal);
          delay = Math.min(delay * 2, 10000);
        }
      }
    },
  };
}
