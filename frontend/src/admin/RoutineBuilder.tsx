import { useEffect, useState } from "react";
import { api } from "./api";

/** Builder visuel : trigger + suite d'actions, sauvegarde en routine. */

type Trigger = { type: "time"; cron: string } | { type: "device"; device_id: string; state: string };
type Action = { tool: string; args: Record<string, any> };

const TOOL_PALETTE: { tool: string; label: string; example: Record<string, any> }[] = [
  { tool: "iot_command", label: "Commande IoT", example: { device_id: "light.salon", action: "on" } },
  { tool: "tts_say", label: "Parler", example: { text: "Bonjour" } },
  { tool: "agent_delegate", label: "Déléguer à un agent", example: { agent: "hermes", goal: "..." } },
  { tool: "presence_set", label: "Mode absence", example: { away: true } },
  { tool: "push_notify", label: "Notif push", example: { title: "Jarvis", body: "..." } },
];

export function RoutineBuilder() {
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<Trigger>({ type: "time", cron: "0 19 * * *" });
  const [actions, setActions] = useState<Action[]>([]);
  const [routines, setRoutines] = useState<any[]>([]);
  const [savedAt, setSavedAt] = useState<number>(0);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.listRoutines().then(setRoutines).catch((e) => setErr(e.message));
  }, [savedAt]);

  const addAction = (tool: string, example: Record<string, any>) => {
    setActions([...actions, { tool, args: { ...example } }]);
  };

  const move = (idx: number, dir: -1 | 1) => {
    const copy = [...actions];
    const j = idx + dir;
    if (j < 0 || j >= copy.length) return;
    [copy[idx], copy[j]] = [copy[j], copy[idx]];
    setActions(copy);
  };

  const remove = (idx: number) => setActions(actions.filter((_, i) => i !== idx));

  const updateArgs = (idx: number, json: string) => {
    try {
      const parsed = JSON.parse(json);
      const copy = [...actions];
      copy[idx] = { ...copy[idx], args: parsed };
      setActions(copy);
    } catch {
      // ignore parse errors during typing
    }
  };

  const save = async () => {
    if (!name.trim() || actions.length === 0) {
      setErr("Donne un nom et au moins une action");
      return;
    }
    try {
      // POST /api/admin/routines (à exposer côté backend)
      await fetch("/api/admin/routines", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("jarvis.token")}`,
        },
        body: JSON.stringify({ name, trigger, actions, enabled: true }),
      });
      setName("");
      setActions([]);
      setSavedAt(Date.now());
      setErr("");
    } catch (e: any) {
      setErr(e.message);
    }
  };

  return (
    <div>
      <h2>Routine Builder</h2>
      <p style={{ opacity: 0.7, fontSize: 13 }}>
        Compose ton trigger + une chaîne d'actions. Sauvegarde-la, elle apparaît dans
        l'onglet Routines.
      </p>

      <div className="card">
        <h3>1. Nom</h3>
        <input
          placeholder='ex: "Soirée détente"'
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ width: "100%" }}
        />
      </div>

      <div className="card">
        <h3>2. Trigger</h3>
        <select
          value={trigger.type}
          onChange={(e) =>
            setTrigger(
              e.target.value === "time"
                ? { type: "time", cron: "0 19 * * *" }
                : { type: "device", device_id: "", state: "on" },
            )
          }
        >
          <option value="time">Heure (cron)</option>
          <option value="device">État d'un device</option>
        </select>
        {trigger.type === "time" && (
          <input
            value={trigger.cron}
            onChange={(e) => setTrigger({ type: "time", cron: e.target.value })}
            placeholder="0 19 * * *  (= tous les jours à 19h)"
            style={{ width: 280 }}
          />
        )}
        {trigger.type === "device" && (
          <>
            <input
              value={trigger.device_id}
              onChange={(e) => setTrigger({ ...trigger, device_id: e.target.value })}
              placeholder="ex: switch.entree"
            />
            <input
              value={trigger.state}
              onChange={(e) => setTrigger({ ...trigger, state: e.target.value })}
              placeholder="on / off / motion"
            />
          </>
        )}
      </div>

      <div className="card">
        <h3>3. Actions ({actions.length})</h3>
        <div style={{ marginBottom: 10 }}>
          <strong style={{ fontSize: 12, opacity: 0.7 }}>Palette :</strong>{" "}
          {TOOL_PALETTE.map((t) => (
            <button key={t.tool} onClick={() => addAction(t.tool, t.example)}>
              + {t.label}
            </button>
          ))}
        </div>
        {actions.map((a, i) => (
          <div
            key={i}
            style={{
              border: "1px solid rgba(255,255,255,0.1)",
              padding: 8,
              borderRadius: 6,
              marginBottom: 6,
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <code>
                {i + 1}. {a.tool}
              </code>
              <span>
                <button onClick={() => move(i, -1)} disabled={i === 0}>
                  ↑
                </button>
                <button onClick={() => move(i, 1)} disabled={i === actions.length - 1}>
                  ↓
                </button>
                <button onClick={() => remove(i)}>✕</button>
              </span>
            </div>
            <textarea
              defaultValue={JSON.stringify(a.args, null, 2)}
              onChange={(e) => updateArgs(i, e.target.value)}
              rows={3}
              style={{ width: "100%", fontFamily: "monospace", fontSize: 12 }}
            />
          </div>
        ))}
      </div>

      <div className="card">
        <button onClick={save} style={{ background: "var(--accent)", color: "#0a0e14" }}>
          Sauvegarder la routine
        </button>
        {err && <span className="error" style={{ marginLeft: 12 }}>{err}</span>}
      </div>

      <div className="card">
        <h3>Routines existantes ({routines.length})</h3>
        <ul style={{ fontSize: 13 }}>
          {routines.map((r) => (
            <li key={r.id}>
              <strong>{r.name}</strong> {r.enabled ? "·" : "(off)"} {r.learned ? "(apprise)" : ""}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
