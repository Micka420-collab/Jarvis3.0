import { useState } from "react";
import { Avatar3D } from "./components/Avatar3D";
import { Waveform } from "./components/Waveform";
import { useVoiceWS } from "./hooks/useVoiceWS";

export default function App() {
  const v = useVoiceWS();
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim()) return;
    v.sendText(text);
    setText("");
  };

  return (
    <>
      <header>
        <span className="brand">Jarvis 3.0</span>
        <span className="status">
          {v.connected ? "● connecté" : "○ déconnecté"} · {v.speaking ? "parle" : "silencieux"}
        </span>
      </header>

      <main>
        <div className="avatar-wrap">
          <Avatar3D speaking={v.speaking} viseme={v.viseme} />
        </div>
        <div className="transcript">
          {v.lines.length === 0 && <div className="status">Dis "bonjour" ou tape un message…</div>}
          {v.lines.map((l, i) => (
            <div key={i} className={`line ${l.who}`}>
              <strong>{l.who === "user" ? "Toi" : l.who === "alert" ? "Argus" : "Jarvis"}</strong>{" "}
              · {l.text}
            </div>
          ))}
        </div>
      </main>

      <footer>
        <button
          className={`mic ${v.recording ? "recording" : ""}`}
          onClick={() => (v.recording ? v.stopRecording() : v.startRecording())}
        >
          {v.recording ? "■ stop" : "● parler"}
        </button>
        <input
          className="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Message texte (Entrée)…"
        />
        <Waveform active={v.recording || v.speaking} />
      </footer>
    </>
  );
}
