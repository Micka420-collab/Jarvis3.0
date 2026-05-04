import { useEffect, useState } from "react";
import { api } from "./api";

export function Dashboard() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e.message));
    const t = setInterval(() => api.dashboard().then(setData).catch(() => undefined), 5000);
    return () => clearInterval(t);
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div>Chargement…</div>;

  return (
    <div className="dashboard">
      <section>
        <h2>État des services</h2>
        <div className="service-grid">
          {Object.entries(data.services).map(([name, ok]) => (
            <div key={name} className={`service ${ok ? "ok" : "ko"}`}>
              <span className="dot" />
              <span>{name}</span>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h2>Compteurs</h2>
        <div className="kpi-grid">
          <Kpi label="Utilisateurs" value={data.counts.users} />
          <Kpi label="Devices" value={data.counts.devices} />
          <Kpi label="Routines" value={data.counts.routines} />
          <Kpi label="Routines en attente" value={data.counts.learned_pending} />
        </div>
      </section>
      <section>
        <h2>Activité 24h</h2>
        <div className="kpi-grid">
          <Kpi label="Auth events" value={data.activity_24h.auth_events} />
          <Kpi label="Raisonnements" value={data.activity_24h.reasoning_traces} />
          <Kpi label="Tâches agents" value={data.activity_24h.agent_tasks} />
        </div>
      </section>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <div className="kpi">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
