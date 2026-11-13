/*
 * Live speech-to-text while the player talks (PROPOSED, D011; owner Will).
 * Mic -> AudioWorklet (16 kHz mono PCM16, ~100 ms chunks) -> WebSocket
 * /voice/live -> server relay (holds the Muse key) -> partial + final text.
 * Audio stays in memory and is never stored. Tracks are released on stop,
 * cancel, failure and unmount. If the live route is missing or fails before
 * it is ready, ``onUnavailable`` fires so the caller can fall back to the
 * record-then-transcribe flow (typing always works).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { MAX_RECORDING_SECONDS } from "./useVoiceRecorder";

export type LiveStatus = "idle" | "connecting" | "listening" | "finishing" | "denied" | "error";

const RATE = 16000;

const WORKLET = `
class Pcm16 extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / ${RATE}; this.buf = []; this.pos = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (; this.pos < ch.length; this.pos += this.ratio) {
      const s = Math.max(-1, Math.min(1, ch[Math.floor(this.pos)]));
      this.buf.push(s < 0 ? s * 0x8000 : s * 0x7fff);
    }
    this.pos -= ch.length;
    if (this.buf.length >= ${RATE / 10}) {
      const pcm = Int16Array.from(this.buf); this.buf = [];
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}
registerProcessor("cst-pcm16", Pcm16);`;

export function isLiveSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.WebSocket !== "undefined" &&
    typeof window.AudioWorkletNode !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

interface Handlers {
  onPartial: (text: string) => void;
  onFinal: (text: string) => void;
  /** The live route is missing or failed before it was ready: fall back. */
  onUnavailable: (message: string) => void;
}

interface Session {
  ws: WebSocket;
  ctx: AudioContext;
  stream: MediaStream;
  ready: boolean;
  queue: ArrayBuffer[];
  stopping: boolean;
  done: boolean;
}

export function useLiveTranscription(url: string | null, handlers: Handlers) {
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const session = useRef<Session | null>(null);
  const timer = useRef<number | null>(null);
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const release = useCallback((s: Session | null) => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    if (!s) return;
    s.stream.getTracks().forEach((t) => t.stop());
    s.ctx.close().catch(() => {});
  }, []);

  const finish = useCallback(
    (s: Session, next: LiveStatus) => {
      if (s.done) return;
      s.done = true;
      release(s);
      try {
        s.ws.close();
      } catch {
        /* already closed */
      }
      if (session.current === s) session.current = null;
      setStatus(next);
    },
    [release],
  );

  const stop = useCallback(() => {
    const s = session.current;
    if (!s || s.stopping) return;
    s.stopping = true;
    if (s.ws.readyState === WebSocket.OPEN) s.ws.send("stop");
    release(s); // mic off right away; the final text is still on its way
    setStatus("finishing");
  }, [release]);

  const cancel = useCallback(() => {
    const s = session.current;
    if (s) finish(s, "idle");
  }, [finish]);

  const start = useCallback(async () => {
    if (!url || session.current) return;
    setError(null);
    setSeconds(0);
    setStatus("connecting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      setStatus((e as Error)?.name === "NotAllowedError" ? "denied" : "error");
      setError("Microphone unavailable.");
      return;
    }
    let ctx: AudioContext;
    let node: AudioWorkletNode;
    try {
      ctx = new AudioContext();
      const moduleUrl = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
      await ctx.audioWorklet.addModule(moduleUrl);
      URL.revokeObjectURL(moduleUrl);
      node = new AudioWorkletNode(ctx, "cst-pcm16");
      ctx.createMediaStreamSource(stream).connect(node); // not to destination: no echo
    } catch {
      stream.getTracks().forEach((t) => t.stop());
      setStatus("idle");
      handlersRef.current.onUnavailable("Live transcription isn't supported here.");
      return;
    }
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    const s: Session = { ws, ctx, stream, ready: false, queue: [], stopping: false, done: false };
    session.current = s;
    node.port.onmessage = ({ data }) => {
      if (s.stopping || s.done) return;
      if (s.ready && ws.readyState === WebSocket.OPEN) ws.send(data as ArrayBuffer);
      else if (s.queue.length < 50) s.queue.push(data as ArrayBuffer); // ~5 s while connecting
    };
    ws.onmessage = ({ data }) => {
      let ev: { type?: string; text?: string; message?: string };
      try {
        ev = JSON.parse(String(data));
      } catch {
        return;
      }
      if (ev.type === "ready") {
        s.ready = true;
        for (const chunk of s.queue) ws.send(chunk);
        s.queue = [];
        setStatus("listening");
        const startedAt = Date.now();
        timer.current = window.setInterval(() => {
          const elapsed = Math.floor((Date.now() - startedAt) / 1000);
          setSeconds(elapsed);
          if (elapsed >= MAX_RECORDING_SECONDS) stop();
        }, 250);
      } else if (ev.type === "partial" && typeof ev.text === "string") {
        handlersRef.current.onPartial(ev.text);
      } else if (ev.type === "final" && typeof ev.text === "string") {
        handlersRef.current.onFinal(ev.text);
        finish(s, "idle");
      } else if (ev.type === "error") {
        const msg = typeof ev.message === "string" ? ev.message : "Live transcription stopped.";
        if (!s.ready) {
          finish(s, "idle");
          handlersRef.current.onUnavailable(msg);
        } else {
          setError(msg);
          finish(s, "error");
        }
      }
    };
    ws.onclose = () => {
      if (s.done) return;
      if (!s.ready) {
        finish(s, "idle");
        handlersRef.current.onUnavailable("Live transcription isn't available.");
      } else {
        setError("Connection lost. Your words so far are kept.");
        finish(s, "error");
      }
    };
  }, [url, finish, stop]);

  useEffect(() => () => {
    const s = session.current;
    if (s) {
      s.done = true;
      release(s);
      try {
        s.ws.close();
      } catch {
        /* closed */
      }
    }
  }, [release]);

  return { status, error, seconds, start, stop, cancel };
}
