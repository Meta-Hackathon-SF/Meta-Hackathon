import type {
  ChatMessage,
  ChatRoom,
  ModerationState,
  MutualReveal,
  SkyStats,
  StreamEvent,
} from "../../../../../contracts/protocol";
import type { ActionContext, ChatActions } from "./ChatPanel";
import { ChatHttpError } from "./client";
import type { ChatClient, StreamState } from "./client";
import { parseMessage } from "./runtime";

export interface LiveSnapshot {
  room?: ChatRoom;
  messages: ChatMessage[];
  reveals: MutualReveal[];
  sky?: SkyStats;
  status: StreamState | "unavailable";
  notice?: string;
}
const empty = (): LiveSnapshot => ({
  messages: [],
  reveals: [],
  status: "connecting",
});
const isAuthError = (error: unknown) =>
  error instanceof ChatHttpError &&
  ["UNAUTHENTICATED", "FORBIDDEN", "CONSENT_REQUIRED"].includes(error.code);

/** Per-mounted-cycle memory only. No answers, tokens or messages go to localStorage. */
export class LiveChatSession {
  private client: ChatClient;
  private cycleId: string;
  private viewerPlayerId: string;
  private value = empty();
  private listeners = new Set<() => void>();
  private controller?: AbortController;
  private cursor = 0;
  private roomLoad = 0;
  private skyLoad = 0;
  private changedAt = new Map<string, number>();
  private moderations = new Map<string, ModerationState>();
  private blockedHandles = new Set<string>();
  private reportedIds = new Set<string>();
  private expiredRooms = new Set<string>();

  constructor(client: ChatClient, cycleId: string, viewerPlayerId: string) {
    this.client = client;
    this.cycleId = cycleId;
    this.viewerPlayerId = viewerPlayerId;
  }
  getSnapshot = () => this.value;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private patch(update: Partial<LiveSnapshot>) {
    this.value = { ...this.value, ...update };
    for (const listener of this.listeners) listener();
  }
  private active(signal: AbortSignal) {
    return !signal.aborted && this.controller?.signal === signal;
  }
  private fail(error: unknown, signal: AbortSignal) {
    if (!this.active(signal)) return;
    if (isAuthError(error)) {
      this.controller?.abort();
      this.changedAt.clear();
      this.patch({
        room: undefined,
        messages: [],
        reveals: [],
        sky: undefined,
        status: "unavailable",
        notice:
          "Your verified session needs attention. Rejoin or restore consent to continue.",
      });
    } else
      this.patch({
        notice: "The chat service is unavailable. You can reconnect.",
      });
  }
  start() {
    this.stop();
    this.value = empty();
    this.cursor = 0;
    this.changedAt.clear();
    this.moderations.clear();
    this.blockedHandles.clear();
    this.reportedIds.clear();
    this.expiredRooms.clear();
    this.controller = new AbortController();
    const signal = this.controller.signal;
    this.patch({});
    void this.refreshSky(signal);
    // Establish the authorized room before replay. The server then replays any
    // events published during these GETs, so historical identities are scoped.
    void this.refreshRoom(signal)
      .then(async () => {
        if (!this.active(signal)) return;
        await this.client.stream({
          signal,
          onState: (state) => {
            if (this.active(signal)) this.patch({ status: state });
          },
          onEvent: (event) =>
            this.active(signal) ? this.event(event, signal) : undefined,
        });
      })
      .catch((error) => this.fail(error, signal));
  }
  stop() {
    this.controller?.abort();
    this.roomLoad += 1;
    this.skyLoad += 1;
  }

  private async refreshRoom(signal: AbortSignal, expectedRoomId?: string) {
    const load = ++this.roomLoad;
    const startSeq = this.cursor;
    try {
      const room = await this.client.getRoom(this.cycleId, signal);
      if (
        !this.active(signal) ||
        load !== this.roomLoad ||
        room.cycleId !== this.cycleId
      )
        return;
      if (expectedRoomId !== undefined && expectedRoomId !== room.roomId)
        return;
      const incoming = await this.client.messages(room.roomId, 0, signal);
      if (!this.active(signal) || load !== this.roomLoad) return;
      const sameRoom = this.value.room?.roomId === room.roomId;
      const merged = new Map(
        incoming.map((message) => [message.messageId, message]),
      );
      if (sameRoom)
        for (const message of this.value.messages) {
          if ((this.changedAt.get(message.messageId) ?? 0) > startSeq)
            merged.set(message.messageId, message);
        }
      if (!sameRoom) {
        this.changedAt.clear();
        this.moderations.clear();
        this.blockedHandles.clear();
        this.reportedIds.clear();
      }
      const handles = new Set(room.members.map((member) => member.handle));
      this.patch({
        room: {
          ...room,
          status: this.expiredRooms.has(room.roomId) ? "expired" : room.status,
          members: room.members.filter(
            (member) =>
              member.isSelf || !this.blockedHandles.has(member.handle),
          ),
        },
        messages: [...merged.values()]
          .filter(
            (message) =>
              message.roomId === room.roomId &&
              !this.blockedHandles.has(message.handle) &&
              (message.kind !== "player" || handles.has(message.handle)),
          )
          .map((message) =>
            this.reportedIds.has(message.messageId)
              ? { ...message, moderation: "hidden_pending" }
              : this.moderations.has(message.messageId)
                ? {
                    ...message,
                    moderation: this.moderations.get(message.messageId)!,
                  }
                : message,
          ),
        reveals:
          sameRoom &&
          room.status === "open" &&
          !this.expiredRooms.has(room.roomId)
            ? this.value.reveals
            : [],
        notice: undefined,
      });
    } catch (error) {
      if (!this.active(signal) || load !== this.roomLoad) return;
      if (error instanceof ChatHttpError && error.code === "NOT_FOUND") {
        this.patch({
          room: undefined,
          messages: [],
          reveals: [],
          notice: "Your constellation room is not available yet.",
        });
      } else this.fail(error, signal);
    }
  }
  private async refreshSky(signal: AbortSignal) {
    const load = ++this.skyLoad;
    try {
      const sky = await this.client.sky(this.cycleId, signal);
      if (this.active(signal) && load === this.skyLoad) this.patch({ sky });
    } catch (error) {
      if (this.active(signal) && load === this.skyLoad && isAuthError(error))
        this.fail(error, signal);
    }
  }
  private async event(event: StreamEvent, signal: AbortSignal) {
    if (event.seq <= this.cursor) return;
    this.cursor = event.seq;
    const room = this.value.room;
    switch (event.type) {
      case "cycle.updated":
        if (event.cycle.cycleId === this.cycleId) {
          await this.refreshRoom(signal);
          void this.refreshSky(signal);
        }
        return;
      case "constellation.revealed":
        await this.refreshRoom(signal, event.roomId);
        return;
      case "sky.updated":
        if (event.cycleId === this.cycleId) void this.refreshSky(signal);
        return;
      case "chat.message": {
        if (
          !room ||
          event.message.roomId !== room.roomId ||
          this.blockedHandles.has(event.message.handle)
        )
          return;
        if (
          event.message.kind === "player" &&
          !room.members.some((member) => member.handle === event.message.handle)
        )
          return;
        this.changedAt.set(event.message.messageId, event.seq);
        this.moderations.set(event.message.messageId, event.message.moderation);
        this.patch({
          messages: [
            ...this.value.messages.filter(
              (message) => message.messageId !== event.message.messageId,
            ),
            event.message,
          ],
        });
        return;
      }
      case "chat.moderated":
        if (
          !room ||
          !this.value.messages.some(
            (message) => message.messageId === event.messageId,
          )
        )
          return;
        this.changedAt.set(event.messageId, event.seq);
        this.moderations.set(event.messageId, event.moderation);
        this.patch({
          messages: this.value.messages.map((message) =>
            message.messageId === event.messageId
              ? { ...message, moderation: event.moderation }
              : message,
          ),
        });
        void this.refreshRoom(signal);
        return;
      case "room.expired":
        if (room?.roomId === event.roomId) {
          this.expiredRooms.add(event.roomId);
          this.patch({ room: { ...room, status: "expired" }, reveals: [] });
        }
        return;
      case "reveal.mutual":
        // The server enforces mutual-pair recipient authorization; the client also
        // rejects every event outside the currently authorized room projection.
        if (
          !room ||
          room.roomId !== event.reveal.roomId ||
          !event.reveal.players.some(
            (player) => player.playerId === this.viewerPlayerId,
          ) ||
          room.status !== "open" ||
          Date.now() >= Date.parse(room.expiresAt)
        )
          return;
        this.patch({
          reveals: [
            ...this.value.reveals.filter(
              (reveal) =>
                reveal.players
                  .map((player) => player.playerId)
                  .sort()
                  .join(":") !==
                event.reveal.players
                  .map((player) => player.playerId)
                  .sort()
                  .join(":"),
            ),
            event.reveal,
          ],
        });
    }
  }
  actions(roomId: string): ChatActions {
    const remote = this.client.actions(roomId);
    const current = () => {
      if (
        !this.controller ||
        this.controller.signal.aborted ||
        this.value.room?.roomId !== roomId
      )
        throw new DOMException("Request canceled", "AbortError");
      return this.controller.signal;
    };
    const act = async (
      context: ActionContext,
      call: () => Promise<unknown>,
    ) => {
      const signal = current();
      try {
        const result = await call();
        if (
          !this.active(signal) ||
          context.signal.aborted ||
          this.value.room?.roomId !== roomId
        )
          throw new DOMException("Request canceled", "AbortError");
        return result;
      } catch (error) {
        if (isAuthError(error)) this.fail(error, signal);
        if (
          error instanceof ChatHttpError &&
          error.code === "ROOM_EXPIRED" &&
          this.active(signal) &&
          this.value.room?.roomId === roomId
        ) {
          this.expiredRooms.add(roomId);
          this.patch({
            room: { ...this.value.room, status: "expired" },
            reveals: [],
          });
        }
        throw error;
      }
    };
    return {
      send: async (text, context) => {
        const value = await act(context, () => remote.send(text, context));
        const message = parseMessage(value);
        const self = this.value.room?.members.find((member) => member.isSelf);
        if (
          message.roomId !== roomId ||
          message.handle !== self?.handle ||
          message.kind !== "player" ||
          message.moderation !== "visible"
        )
          throw new ChatHttpError("PROVIDER_UNAVAILABLE");
        this.changedAt.set(message.messageId, this.cursor + 1);
        this.patch({
          messages: [
            ...this.value.messages.filter(
              (m) => m.messageId !== message.messageId,
            ),
            message,
          ],
        });
        return message;
      },
      report: async (messageId, handle, reason, context) => {
        await act(context, () =>
          remote.report(messageId, handle, reason, context),
        );
        this.reportedIds.add(messageId);
        this.changedAt.set(messageId, this.cursor + 1);
        this.patch({
          messages: this.value.messages.map((message) =>
            message.messageId === messageId
              ? { ...message, moderation: "hidden_pending" }
              : message,
          ),
        });
      },
      block: async (handle, context) => {
        await act(context, () => remote.block(handle, context));
        this.blockedHandles.add(handle);
        const room = this.value.room!;
        this.patch({
          room: {
            ...room,
            members: room.members.filter(
              (member) => member.handle !== handle || member.isSelf,
            ),
          },
          messages: this.value.messages.filter(
            (message) => message.handle !== handle,
          ),
          reveals: [],
        });
      },
      reveal: (handle, context) =>
        act(context, () => remote.reveal(handle, context)),
    };
  }
}
