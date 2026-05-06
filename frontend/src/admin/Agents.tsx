import { useEffect, useState } from "react";
import { api } from "./api";

export function Agents() {
  const [agents, setAgents] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [agent, setAgent] = useState("hermes");
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    try {
      const [a, t] = await Promise.all([api.listAgents(), api.listAgentTasks()]);
      setAgents(a as any[]);
      setTasks(t as any[]);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    reload();
    const i = setInterval(reload, 5000);
    return () => clearInterval(i);
  }, []);

  const delegate = async () => {
    if (!goal.trim()) return;
    setBusy(true);
    try {
      await api.delegate(agent, goal);
      setGoal("");
      reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h2>Agents externes</h2>
      <div className="card">
        <h3>Agents disponibles</h3>
        <table className="grid">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Disponible</th>
              <th>Commande</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.name}>
                <td>
                  <strong>{a.name}</strong>
                </td>
                <td>{a.available ? "✓" : "✗"}</td>
                <td>
                  <code>{a.command}</code>
                </td>
                <td>{a.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Déléguer une tâche</h3>
        <select value={agent} onChange={(e) => setAgent(e.target.value)}>
          {agents
            .filter((a) => a.available)
            .map((a) => (
              <option key={a.name}>{a.name}</option>
            ))}
        </select>
        <textarea
          rows={3}
          placeholder="Ex: 'classe mes téléchargements par type dans ~/Downloads'"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
        />
        <button onClick={delegate} disabled={busy || !goal.trim()}>
          {busy ? "..." : "Déléguer"}
        </button>
      </div>

      <div className="card">
        <h3>Tâches récentes ({tasks.length})</h3>
        <table className="grid">
          <thead>
            <tr>
              <th>Date</th>
              <th>Agent</th>
              <th>Goal</th>
              <th>État</th>
              <th>Exit</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{new Date(t.created_at).toLocaleString()}</td>
                <td>{t.agent}</td>
                <td title={t.goal}>{t.goal.slice(0, 60)}</td>
                <td>
                  <span className={`badge status-${t.status}`}>{t.status}</span>
                </td>
                <td>{t.exit_code ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
