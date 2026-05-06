import { useEffect, useState } from "react";
import { api } from "./api";

type TestKind =
  | "homeassistant"
  | "argus"
  | "frigate"
  | "anthropic"
  | "openrouter"
  | "ollama"
  | "mqtt";
type TestResult = { ok: boolean; detail: string; latency_ms: number };

export function Connections() {
  const [state, setState] = useState<any>(null);
  const [results, setResults] = useState<Record<string, TestResult>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");

  // Forms (non-persistées : on teste, le wizard CLI persiste)
  const [haUrl, setHaUrl] = useState("");
  const [haTok, setHaTok] = useState("");
  const [argUrl, setArgUrl] = useState("");
  const [argTok, setArgTok] = useState("");
  const [frUrl, setFrUrl] = useState("http://frigate:5000");
  const [anthKey, setAnthKey] = useState("");
  const [anthModel, setAnthModel] = useState("claude-sonnet-4-6");
  const [orKey, setOrKey] = useState("");
  const [orModel, setOrModel] = useState("anthropic/claude-sonnet-4-6");
  const [olUrl, setOlUrl] = useState("http://ollama:11434");

  const reload = () =>
    api.wizardState()
      .then((s: any) => {
        setState(s);
        if (s.homeassistant?.url) setHaUrl(s.homeassistant.url);
        if (s.argus?.url) setArgUrl(s.argus.url);
        if (s.frigate?.url) setFrUrl(s.frigate.url);
        if (s.llm?.model) setAnthModel(s.llm.model);
      })
      .catch((e) => setErr(e.message));

  useEffect(() => {
    reload();
  }, []);

  const test = async (kind: TestKind, body: any) => {
    setBusy(kind);
    setErr("");
    try {
      const r = (await api.wizardTest({ kind, ...body })) as TestResult;
      setResults({ ...results, [kind]: r });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };

  const Status = ({ kind }: { kind: TestKind }) => {
    const r = results[kind];
    if (busy === kind) return <span className="badge">test…</span>;
    if (!r) return null;
    return (
      <span className={`badge ${r.ok ? "status-completed" : "status-failed"}`}>
        {r.ok ? "✓ OK" : "✗"} {r.latency_ms}ms — {r.detail.slice(0, 80)}
      </span>
    );
  };

  return (
    <div>
      <h2>Connexions</h2>
      <p style={{ opacity: 0.7, fontSize: 13 }}>
        Teste chaque service connecté à Jarvis. Les valeurs ici ne sont <em>pas</em>
        persistées — utilise <code>make wizard</code> en CLI pour les écrire dans
        <code>.env</code>.
      </p>

      {err && <div className="error">{err}</div>}

      {state && (
        <div className="card">
          <h3>État courant</h3>
          <table className="grid">
            <tbody>
              <tr>
                <td>LLM</td>
                <td>
                  <strong>{state.llm.provider}</strong> · {state.llm.model || "(par défaut)"}
                  {state.llm.anthropic_configured && " · Anthropic key ✓"}
                </td>
              </tr>
              <tr>
                <td>Home Assistant</td>
                <td>
                  {state.homeassistant.url || "—"}
                  {state.homeassistant.token_present && " · token ✓"}
                </td>
              </tr>
              <tr>
                <td>Argus</td>
                <td>
                  {state.argus.url || "—"}
                  {state.argus.token_present && " · token ✓"}
                </td>
              </tr>
              <tr>
                <td>Frigate (Vision)</td>
                <td>{state.frigate.url || "—"}</td>
              </tr>
              <tr>
                <td>Web Push</td>
                <td>{state.vapid.configured ? "✓ VAPID configuré" : "✗ pas de VAPID"}</td>
              </tr>
              <tr>
                <td>Agents</td>
                <td>
                  Hermes: {state.agents.hermes ? "✓" : "—"} · OpenClaw: {state.agents.openclaw ? "✓" : "—"}
                </td>
              </tr>
              <tr>
                <td>Voix-print enrôlée</td>
                <td>{state.voice_enrolled_users} utilisateur(s)</td>
              </tr>
              <tr>
                <td>Visage enrôlé</td>
                <td>{state.face_enrolled_users} utilisateur(s)</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h3>1. LLM Anthropic Claude</h3>
        <input placeholder="sk-ant-..." value={anthKey} onChange={(e) => setAnthKey(e.target.value)} />
        <input placeholder="claude-sonnet-4-6" value={anthModel} onChange={(e) => setAnthModel(e.target.value)} />
        <button
          disabled={busy === "anthropic" || !anthKey}
          onClick={() => test("anthropic", { api_key: anthKey, extra: { model: anthModel } })}
        >
          Tester
        </button>{" "}
        <Status kind="anthropic" />
      </div>

      <div className="card">
        <h3>1bis. LLM OpenRouter (200+ modèles)</h3>
        <input
          placeholder="sk-or-v1-..."
          value={orKey}
          onChange={(e) => setOrKey(e.target.value)}
          type="password"
        />
        <input
          placeholder="anthropic/claude-sonnet-4-6"
          value={orModel}
          onChange={(e) => setOrModel(e.target.value)}
        />
        <button
          disabled={busy === "openrouter" || !orKey}
          onClick={() => test("openrouter", { api_key: orKey, extra: { model: orModel } })}
        >
          Tester
        </button>{" "}
        <Status kind="openrouter" />
        <p style={{ fontSize: 11, opacity: 0.6, marginTop: 6 }}>
          Récupère ta clé sur openrouter.ai/keys · une seule clé pour Claude, GPT,
          Llama, Gemini, Mistral, etc.
        </p>
      </div>

      <div className="card">
        <h3>1ter. LLM Ollama (local)</h3>
        <input placeholder="http://ollama:11434" value={olUrl} onChange={(e) => setOlUrl(e.target.value)} />
        <button disabled={busy === "ollama"} onClick={() => test("ollama", { url: olUrl })}>
          Tester
        </button>{" "}
        <Status kind="ollama" />
      </div>

      <div className="card">
        <h3>2. Home Assistant</h3>
        <input placeholder="http://homeassistant:8123" value={haUrl} onChange={(e) => setHaUrl(e.target.value)} />
        <input
          placeholder="Long-lived access token"
          value={haTok}
          onChange={(e) => setHaTok(e.target.value)}
          type="password"
        />
        <button
          disabled={busy === "homeassistant" || !haUrl || !haTok}
          onClick={() => test("homeassistant", { url: haUrl, token: haTok })}
        >
          Tester
        </button>{" "}
        <Status kind="homeassistant" />
      </div>

      <div className="card">
        <h3>3. Argus (alertes réseau)</h3>
        <input placeholder="http://argus:9000" value={argUrl} onChange={(e) => setArgUrl(e.target.value)} />
        <input
          placeholder="Token API (optionnel)"
          value={argTok}
          onChange={(e) => setArgTok(e.target.value)}
          type="password"
        />
        <button
          disabled={busy === "argus" || !argUrl}
          onClick={() => test("argus", { url: argUrl, token: argTok })}
        >
          Tester
        </button>{" "}
        <Status kind="argus" />
      </div>

      <div className="card">
        <h3>4. Frigate (Claude Vision)</h3>
        <input placeholder="http://frigate:5000" value={frUrl} onChange={(e) => setFrUrl(e.target.value)} />
        <button disabled={busy === "frigate" || !frUrl} onClick={() => test("frigate", { url: frUrl })}>
          Tester
        </button>{" "}
        <Status kind="frigate" />
      </div>

      <div className="card">
        <h3>5. MQTT / IoT (interne)</h3>
        <button disabled={busy === "mqtt"} onClick={() => test("mqtt", {})}>
          Tester le service IoT
        </button>{" "}
        <Status kind="mqtt" />
      </div>

      <div className="card">
        <h3>Étapes manuelles</h3>
        <ul style={{ lineHeight: 1.7 }}>
          <li>
            <strong>Voix-print</strong> : enregistre la voix de chaque membre depuis l'onglet
            <em> Membres</em> ou via <code>make enroll-voice</code>
          </li>
          <li>
            <strong>Multi-room</strong> : édite{" "}
            <code>services/voice/app/speakers.yaml</code> puis <code>docker compose restart voice</code>
          </li>
          <li>
            <strong>Push notifications</strong> : ouvre l'app sur ton téléphone et clique
            "Activer les notifications" (PWA installable)
          </li>
          <li>
            <strong>Wizard complet en CLI</strong> :{" "}
            <code>cd ~/Jarvis3.0 &amp;&amp; make wizard</code>
          </li>
        </ul>
      </div>
    </div>
  );
}
