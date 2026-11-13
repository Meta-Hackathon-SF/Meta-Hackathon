/*
 * Recording -> WAV, in the browser (owner: Will).
 * Muse Voice Transcribe accepts only mono 16-bit PCM WAV at 16 or 24 kHz, but
 * phones record webm/opus or mp4/aac. The recording is decoded, mixed to mono,
 * resampled to 16 kHz and re-encoded here, in memory, before upload.
 * 60 seconds is about 1.9 MB.
 */
export const WAV_SAMPLE_RATE = 16000;

/** Encode mono float samples (-1..1) as a 16-bit PCM WAV file. */
export function encodeWav(samples: Float32Array, sampleRate: number = WAV_SAMPLE_RATE): Blob {
  const bytes = samples.length * 2;
  const view = new DataView(new ArrayBuffer(44 + bytes));
  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + bytes, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // integer PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  ascii(36, "data");
  view.setUint32(40, bytes, true);
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, Math.round(clamped * 0x7fff), true);
  }
  return new Blob([view.buffer], { type: "audio/wav" });
}

/** Decode any recording the browser can play and return 16 kHz mono WAV. */
export async function toWav(recording: Blob): Promise<Blob> {
  const AudioContextClass =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass || typeof OfflineAudioContext === "undefined")
    throw new Error("This browser cannot prepare audio for transcription.");
  const context = new AudioContextClass();
  let decoded: AudioBuffer;
  try {
    decoded = await context.decodeAudioData(await recording.arrayBuffer());
  } finally {
    void context.close();
  }
  const frames = Math.max(1, Math.ceil(decoded.duration * WAV_SAMPLE_RATE));
  // One output channel: the offline context down-mixes and resamples.
  const offline = new OfflineAudioContext(1, frames, WAV_SAMPLE_RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  return encodeWav(rendered.getChannelData(0), WAV_SAMPLE_RATE);
}
