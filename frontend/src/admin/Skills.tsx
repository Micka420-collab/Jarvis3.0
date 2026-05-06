import { useEffect, useState } from "react";
import { api } from "./api";

export function Skills() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const reload = () => api.listSkills().then(setData).catch((e) => setErr(e.message));
  useEffect(() => {
    reload();
  }, []);

  const reloadSkills = async () => {
    setBusy(true);
    try {
      await api.reloadSkills();
      await reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="row-actions">
        <h2>Skills ({data?.skills?.length || 0})</h2>
        <button onClick={reloadSkills} disabled={busy}>
          {busy ? "..." : "Hot-reload"}
        </button>
      </div>
      {err && <div className="error">{err}</div>}
      {data?.skills?.map((s: any) => (
        <div key={s.name} className="card">
          <h3>{s.name}</h3>
          <p>{s.description}</p>
          <div>
            <strong>Tools:</strong>{" "}
            {s.tools.map((t: string) => (
              <code key={t} style={{ marginRight: 8 }}>
                {t}
              </code>
            ))}
          </div>
          {s.crons.length > 0 && (
            <div>
              <strong>Cron:</strong> {s.crons.join(", ")}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
