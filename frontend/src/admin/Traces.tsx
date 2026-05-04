import { useEffect, useState } from "react";
import { api } from "./api";

export function Traces() {
  const [traces, setTraces] = useState<any[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.listTraces(100).then(setTraces).catch((e) => setErr(e.message));
    const i = setInterval(
      () => api.listTraces(100).then(setTraces).catch(() => undefined),
      5000,
    );
    return () => clearInterval(i);
  }, []);

  return (
    <div>
      <h2>Traces de raisonnement</h2>
      <p style={{ opacity: 0.7, fontSize: 13 }}>
        Chaque tour de Jarvis est tracé : ce qui a été dit, ce qu'il a déduit, quels tools il a
        appelés, combien de temps ça a pris.
      </p>
      {err && <div className="error">{err}</div>}
      <table className="grid">
        <thead>
          <tr>
            <th>Date</th>
            <th>Question</th>
            <th>Intent</th>
            <th>Tools</th>
            <th>Réponse</th>
            <th>Latence</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((t) => (
            <tr key={t.id}>
              <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>
                {new Date(t.ts).toLocaleString()}
              </td>
              <td>{t.user_text}</td>
              <td>
                <span className="badge">{t.intent}</span>
              </td>
              <td>
                {(t.tools_called || []).map((c: any, i: number) => (
                  <code key={i} style={{ marginRight: 6 }}>
                    {c.name || c.tool || JSON.stringify(c).slice(0, 30)}
                  </code>
                ))}
              </td>
              <td title={t.response} style={{ maxWidth: 400 }}>
                {(t.response || "").slice(0, 120)}
                {(t.response || "").length > 120 ? "…" : ""}
              </td>
              <td>{t.duration_ms} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
