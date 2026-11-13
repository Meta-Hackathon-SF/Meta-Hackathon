import { useEffect, useRef, useState } from "react";
import type { CycleClient } from "../client";
import { isLiveSupported, useLiveTranscription } from "../useLiveTranscription";
import { MAX_CHARS, message } from "../useDaily";
import { useVoiceRecorder } from "../useVoiceRecorder";

/**
 * Mic button behaviour for the Space composer: live words while talking when the
 * server offers it (D013), otherwise record then transcribe. Audio is never kept.
 * Typing always works; every failure leaves a note and the text box usable.
 */
export function useVoiceInput(client: CycleClient, setText: (text: string) => void) {
  const [note, setNote] = useState<string | null>(null);
  const [usedVoice, setUsedVoice] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const setTextRef = useRef(setText);
  useEffect(() => {
    setTextRef.current = setText;
  });

  const recorder = useVoiceRecorder(async (audio) => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setTranscribing(true);
    setNote("Transcribing…");
    try {
      const result = await client.transcribe(audio, controller.signal);
      if (controller.signal.aborted) return;
      setTextRef.current(result.transcript.slice(0, MAX_CHARS));
      setUsedVoice(true);
      setNote(result.mode === "fixture" ? "Fixture transcript, not your voice. Edit it before posting." : "Check the words, then post.");
    } catch (err) {
      if (!controller.signal.aborted) setNote(`${message(err)} You can type instead.`);
    } finally {
      if (!controller.signal.aborted) setTranscribing(false);
    }
  });
  useEffect(() => () => pending.current?.abort(), []);

  const [liveOff, setLiveOff] = useState(false);
  const liveUrl = !liveOff && isLiveSupported() ? (client.liveTranscriptionUrl?.() ?? null) : null;
  const live = useLiveTranscription(liveUrl, {
    onPartial: (spoken) => {
      setTextRef.current(spoken.slice(0, MAX_CHARS));
      setUsedVoice(true);
    },
    onFinal: (spoken) => {
      if (spoken) setTextRef.current(spoken.slice(0, MAX_CHARS));
      setUsedVoice(true);
      setNote(spoken ? "Check the words, then post." : "No words came through. Try again or type.");
    },
    onUnavailable: () => {
      setLiveOff(true);
      void recorder.start();
    },
  });

  const liveActive = live.status === "connecting" || live.status === "listening";
  const recording = recorder.status === "recording" || liveActive;
  const blocked = recorder.status === "denied" || recorder.status === "unsupported" || live.status === "denied";

  const hint = recording
    ? "Listening… tap to stop"
    : transcribing
      ? "Transcribing…"
      : recorder.status === "denied" || live.status === "denied"
        ? "Mic is off. Typing works the same."
        : recorder.status === "unsupported"
          ? "This browser can't record. Type instead."
          : note ?? "or just talk";

  const toggle = () => {
    if (recording) {
      if (liveActive) live.stop();
      else recorder.stop();
      return;
    }
    setNote(null);
    if (liveUrl) void live.start();
    else void recorder.start();
  };

  const reset = () => {
    pending.current?.abort();
    recorder.cancel();
    live.cancel();
    setNote(null);
    setUsedVoice(false);
    setTranscribing(false);
  };

  return { recording, blocked, hint, toggle, reset, source: (usedVoice ? "voice" : "text") as "voice" | "text" };
}
