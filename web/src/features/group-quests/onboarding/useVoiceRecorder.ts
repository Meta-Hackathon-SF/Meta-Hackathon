import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderStatus =
  | "idle"
  | "requesting"
  | "recording"
  | "unsupported"
  | "denied"
  | "error";

export const MAX_RECORDING_SECONDS = 60;

const PREFERRED_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4"];

export function isRecordingSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

/**
 * Microphone capture via the browser MediaRecorder API. Audio stays in memory
 * and is handed to the caller as a Blob; nothing is stored. Tracks are always
 * released on stop, cancel and unmount.
 */
export function useVoiceRecorder(onRecorded: (audio: Blob) => void) {
  const [status, setStatus] = useState<RecorderStatus>(() =>
    isRecordingSupported() ? "idle" : "unsupported",
  );
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const discard = useRef(false);
  const timer = useRef<number | null>(null);
  const attempt = useRef(0);
  const onRecordedRef = useRef(onRecorded);
  useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const release = useCallback(() => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    recorder.current = null;
  }, []);

  const stop = useCallback(() => {
    const active = recorder.current;
    if (active && active.state !== "inactive") active.stop();
    else release();
  }, [release]);

  const cancel = useCallback(() => {
    attempt.current++;
    discard.current = true;
    stop();
    release();
    setSeconds(0);
    setStatus(isRecordingSupported() ? "idle" : "unsupported");
  }, [release, stop]);

  const start = useCallback(async () => {
    if (!isRecordingSupported()) {
      setStatus("unsupported");
      return;
    }
    const current = ++attempt.current;
    setError(null);
    setStatus("requesting");
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      if (current !== attempt.current) return;
      const name = (err as DOMException)?.name;
      if (name === "NotAllowedError" || name === "SecurityError") {
        setStatus("denied");
      } else {
        setStatus("error");
        setError(
          name === "NotFoundError"
            ? "No microphone was found."
            : "The microphone could not be started.",
        );
      }
      return;
    }
    if (current !== attempt.current) {
      media.getTracks().forEach((track) => track.stop());
      return;
    }
    const mimeType = PREFERRED_TYPES.find((type) =>
      typeof MediaRecorder.isTypeSupported === "function"
        ? MediaRecorder.isTypeSupported(type)
        : false,
    );
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(media, mimeType ? { mimeType } : undefined);
    } catch {
      media.getTracks().forEach((track) => track.stop());
      setStatus("error");
      setError("This browser cannot record audio.");
      return;
    }
    stream.current = media;
    recorder.current = rec;
    chunks.current = [];
    discard.current = false;
    rec.ondataavailable = (event) => {
      if (event.data && event.data.size) chunks.current.push(event.data);
    };
    rec.onstop = () => {
      const blob = new Blob(chunks.current, { type: rec.mimeType || mimeType || "audio/webm" });
      chunks.current = [];
      release();
      if (current !== attempt.current || discard.current) return;
      setStatus("idle");
      if (blob.size) onRecordedRef.current(blob);
      else setError("No audio was captured. Try again or type instead.");
    };
    rec.start();
    setSeconds(0);
    setStatus("recording");
    const startedAt = Date.now();
    timer.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_RECORDING_SECONDS) stop();
    }, 250);
  }, [release, stop]);

  useEffect(
    () => () => {
      attempt.current++;
      discard.current = true;
      const active = recorder.current;
      if (active && active.state !== "inactive") active.stop();
      if (timer.current !== null) window.clearInterval(timer.current);
      stream.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  return { status, error, seconds, start, stop, cancel };
}
