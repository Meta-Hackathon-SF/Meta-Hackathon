/*
 * Demo-mode speech to text using the browser's own SpeechRecognition. Used ONLY with the fixture
 * client (no backend voice route), so the mic actually works in a local demo instead of returning a
 * canned sentence. In Chrome this engine may send audio to the browser vendor, so the UI labels it
 * "Browser speech (demo)". The production path stays Muse live STT (D013) through the server.
 */
import { useCallback, useEffect, useRef, useState } from "react";

interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface RecognitionEvent {
  resultIndex: number;
  results: ArrayLike<RecognitionResult>;
}
interface Recognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type Ctor = new () => Recognition;

const ctor = (): Ctor | null => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: Ctor; webkitSpeechRecognition?: Ctor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

export const isBrowserSpeechSupported = () => ctor() !== null;

export type BrowserSpeechStatus = "idle" | "listening" | "denied" | "error";

export function useBrowserSpeech(handlers: { onText: (text: string) => void; onDone: (text: string) => void }) {
  const [status, setStatus] = useState<BrowserSpeechStatus>("idle");
  const rec = useRef<Recognition | null>(null);
  const text = useRef("");
  const h = useRef(handlers);
  useEffect(() => {
    h.current = handlers;
  });
  useEffect(() => () => rec.current?.abort(), []);

  const start = useCallback(() => {
    const Ctor = ctor();
    if (!Ctor) return;
    const r = new Ctor();
    r.continuous = true;
    r.interimResults = true;
    r.lang = navigator.language || "en-US";
    text.current = "";
    r.onresult = (e) => {
      let spoken = "";
      for (let i = 0; i < e.results.length; i++) spoken += `${e.results[i][0].transcript} `;
      text.current = spoken.trim();
      h.current.onText(text.current);
    };
    r.onerror = (e) => setStatus(e.error === "not-allowed" || e.error === "service-not-allowed" ? "denied" : "error");
    r.onend = () => {
      rec.current = null;
      setStatus((s) => (s === "listening" ? "idle" : s));
      h.current.onDone(text.current);
    };
    rec.current = r;
    setStatus("listening");
    try {
      r.start();
    } catch {
      setStatus("error");
    }
  }, []);

  const stop = useCallback(() => rec.current?.stop(), []);
  const cancel = useCallback(() => {
    rec.current?.abort();
    rec.current = null;
    setStatus("idle");
  }, []);
  return { status, start, stop, cancel };
}
