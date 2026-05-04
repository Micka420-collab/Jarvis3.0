import { useState } from "react";
import { AvatarGLTF } from "./components/AvatarGLTF";
import { Floorplan } from "./components/Floorplan";
import { Waveform } from "./components/Waveform";
import { useVoiceWS } from "./hooks/useVoiceWS";
import { usePushNotifications } from "./hooks/usePushNotifications";

type Tab = "avatar" | "house";

export default function App() {
  const v = useVoiceWS();
  const [text, setText] = useState("");
  const [tab, setTab] = useState<Tab>("avatar");
  const [explanation, setExplanation] = useState<string>("");
  const push = usePushNotifications();

  const submit = () => {
    if (!text.trim()) return;
    v.sendText(text);
    setText("");
  };

  const askWhy = async () => {
    if (!v.sessionId) return;
    try {
      const r = await fetch(`/api/explain/last?session_id=${encodeURIComponent(v.sessionId)}`);
      if (!r.ok) {
        setExplanation("Pas de trace disponible.");
        return;
      }
      const d = await r.json();
      setExplanation(
        `Tu m'as dit : « ${d.user_text} ». Intent : ${d.intent}. ` +
          (d.tools && d.tools.length ? `Tools : ${d.tools.map((t: any) => t.name).join(", ")}. ` : "") +
          `Latence : ${d.duration_ms} ms.`,
      );
    } catch {
      setExplanation("Erreur lors de la récupération.");
    }
  };

  return (
    <>
      <header>
        <span className="brand">Jarvis 3.0</span>
        <nav style={{ display: "flex", gap: 8 }}>
          <button className={`tab ${tab === "avatar" ? "on" : ""}`} onClick={() => setTab("avatar")}>
            Avatar
          </button>
          <button className={`tab ${tab === "house" ? "on" : ""}`} onClick={() => setTab("house")}>
            Maison
          </button>
        </nav>
        <span className="status">
          {v.connected ? "● connecté" : "○ déconnecté"} · {v.speaking ? "parle" : "silencieux"}
          {push.status === "available" && (
            <button className="link" style={{ marginLeft: 12 }} onClick={push.subscribe}>
              Activer les notifications
            </button>
          )}
        </span>
      </header>

      <main>
        <div className="avatar-wrap">
          {tab === "avatar" ? (
            <AvatarGLTF speaking={v.speaking} viseme={v.viseme} />
          ) : (
            <Floorplan />
          )}
        </div>
        <div className="transcript">
          {v.lines.length === 0 && !v.partial && (
            <div className="status">Dis "bonjour" ou tape un message…</div>
          )}
          {v.lines.map((l, i) => (
            <div key={i} className={`line ${l.who}`}>
              <strong>{l.who === "user" ? "Toi" : l.who === "alert" ? "Argus" : "Jarvis"}</strong>{" "}
              · {l.text}
            </div>
          ))}
          {v.partial && (
            <div className="line partial">
              <strong>Toi</strong> · <em style={{ opacity: 0.55 }}>{v.partial}…</em>
            </div>
          )}
          {explanation && (
            <div className="line bot">
              <strong>Trace</strong> · <em>{explanation}</em>
            </div>
          )}
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
        <button className="link" onClick={askWhy} title="Explique-moi">
          Pourquoi ?
        </button>
        <Waveform active={v.recording || v.speaking} />
      </footer>
    </>
  );
}
