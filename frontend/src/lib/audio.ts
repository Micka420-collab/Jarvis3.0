/** Capture micro PCM 16-bit mono 16 kHz via AudioWorklet, et lecture TTS streaming. */

export class MicrophoneCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;

  async start(onChunk: (pcm16: Int16Array) => void): Promise<void> {
    this.ctx = new AudioContext({ sampleRate: 16000 });
    await this.ctx.audioWorklet.addModule(workletURL());
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm-capture");
    this.node.port.onmessage = (ev) => onChunk(new Int16Array(ev.data));
    source.connect(this.node);
  }

  stop(): void {
    this.node?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.node = this.stream = this.ctx = null;
  }
}

function workletURL(): string {
  const code = `
    class PCMCapture extends AudioWorkletProcessor {
      process(inputs) {
        const input = inputs[0];
        if (!input || !input[0]) return true;
        const ch = input[0];
        const out = new Int16Array(ch.length);
        for (let i = 0; i < ch.length; i++) {
          const s = Math.max(-1, Math.min(1, ch[i]));
          out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(out.buffer, [out.buffer]);
        return true;
      }
    }
    registerProcessor("pcm-capture", PCMCapture);
  `;
  const blob = new Blob([code], { type: "application/javascript" });
  return URL.createObjectURL(blob);
}

/** Lecteur PCM 16-bit mono streaming, interruptible (barge-in). */
export class PCMPlayer {
  private ctx: AudioContext;
  private playhead = 0;
  private sources: AudioBufferSourceNode[] = [];
  constructor(public sampleRate = 22050) {
    this.ctx = new AudioContext({ sampleRate });
    this.playhead = this.ctx.currentTime;
  }
  pushChunk(pcmBase64: string): void {
    const bytes = Uint8Array.from(atob(pcmBase64), (c) => c.charCodeAt(0));
    const i16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x8000;
    const buffer = this.ctx.createBuffer(1, f32.length, this.sampleRate);
    buffer.copyToChannel(f32, 0);
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.ctx.destination);
    const startAt = Math.max(this.ctx.currentTime, this.playhead);
    src.start(startAt);
    this.playhead = startAt + buffer.duration;
    this.sources.push(src);
    src.onended = () => {
      const i = this.sources.indexOf(src);
      if (i >= 0) this.sources.splice(i, 1);
    };
  }
  /** Coupe immédiatement tous les chunks en queue ou en cours. */
  stop(): void {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        // already stopped
      }
    }
    this.sources = [];
    this.playhead = this.ctx.currentTime;
  }
  reset(): void {
    this.stop();
  }
}

export function int16ToBase64(arr: Int16Array): string {
  const bytes = new Uint8Array(arr.buffer);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
