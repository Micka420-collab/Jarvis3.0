import { useCallback, useEffect, useRef, useState } from "react";
import { MicrophoneCapture, PCMPlayer, int16ToBase64 } from "../lib/audio";

export type Line = { who: "user" | "bot" | "alert"; text: string; ts: number };

export function useVoiceWS() {
  const wsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MicrophoneCapture | null>(null);
  const playerRef = useRef<PCMPlayer | null>(null);
  const [connected, setConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [viseme, setViseme] = useState<string>("sil");
  const [lines, setLines] = useState<Line[]>([]);

  const append = (line: Line) => setLines((prev) => [...prev, line].slice(-50));

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/voice`);
    wsRef.current = ws;
    playerRef.current = new PCMPlayer(22050);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "transcript") {
        append({ who: "user", text: msg.text, ts: Date.now() });
      } else if (msg.type === "tts_chunk") {
        if (msg.pcm_b64) playerRef.current?.pushChunk(msg.pcm_b64);
        if (msg.viseme) setViseme(msg.viseme);
        if (msg.is_final) {
          setSpeaking(false);
          setViseme("sil");
        } else {
          setSpeaking(true);
        }
      }
    };
    return () => ws.close();
  }, []);

  const send = useCallback((obj: object) => {
    wsRef.current?.send(JSON.stringify(obj));
  }, []);

  const startRecording = useCallback(async () => {
    if (recording) return;
    const mic = new MicrophoneCapture();
    await mic.start((pcm) => send({ type: "audio", pcm_b64: int16ToBase64(pcm) }));
    micRef.current = mic;
    setRecording(true);
  }, [recording, send]);

  const stopRecording = useCallback(() => {
    micRef.current?.stop();
    micRef.current = null;
    send({ type: "end" });
    setRecording(false);
  }, [send]);

  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      append({ who: "user", text, ts: Date.now() });
      send({ type: "text", text });
    },
    [send],
  );

  return {
    connected,
    recording,
    speaking,
    viseme,
    lines,
    appendBotLine: (text: string) => append({ who: "bot", text, ts: Date.now() }),
    startRecording,
    stopRecording,
    sendText,
  };
}
