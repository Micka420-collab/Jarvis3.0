import { useEffect, useState } from "react";
import { api } from "./api";

export function Routines() {
  const [items, setItems] = useState<any[]>([]);
  const [err, setErr] = useState("");

  const reload = () => api.listRoutines().then(setItems).catch((e) => setErr(e.message));
  useEffect(() => {
    reload();
  }, []);

  const toggle = async (r: any) => {
    await api.toggleRoutine(r.id, !r.enabled);
    reload();
  };
  const remove = async (r: any) => {
    if (!confirm(`Supprimer la routine '${r.name}' ?`)) return;
    await api.deleteRoutine(r.id);
    reload();
  };

  const learnedPending = items.filter((r) => r.learned && !r.enabled);
  const active = items.filter((r) => r.enabled);
  const others = items.filter((r) => !r.learned && !r.enabled);

  return (
    <div>
      <h2>Routines</h2>

      {learnedPending.length > 0 && (
        <section>
          <h3>📍 Suggestions apprises ({learnedPending.length})</h3>
          <p style={{ opacity: 0.7, fontSize: 13 }}>
            Jarvis a remarqué ces patterns dans tes habitudes. Active celles que tu veux automatiser.
          </p>
          {learnedPending.map((r) => (
            <RoutineRow key={r.id} r={r} onToggle={toggle} onDelete={remove} />
          ))}
        </section>
      )}

      <section>
        <h3>⚡ Actives ({active.length})</h3>
        {active.map((r) => (
          <RoutineRow key={r.id} r={r} onToggle={toggle} onDelete={remove} />
        ))}
      </section>

      {others.length > 0 && (
        <section>
          <h3>Inactives ({others.length})</h3>
          {others.map((r) => (
            <RoutineRow key={r.id} r={r} onToggle={toggle} onDelete={remove} />
          ))}
        </section>
      )}

      {err && <div className="error">{err}</div>}
    </div>
  );
}

function RoutineRow({
  r,
  onToggle,
  onDelete,
}: {
  r: any;
  onToggle: (r: any) => void;
  onDelete: (r: any) => void;
}) {
  return (
    <div className="routine">
      <div>
        <strong>{r.name}</strong>{" "}
        {r.learned && <span className="badge tr-mqtt">apprise</span>}{" "}
        {r.confidence > 0 && (
          <span style={{ opacity: 0.6, fontSize: 12 }}>
            confiance {Math.round(r.confidence * 100)}%
          </span>
        )}
        <div style={{ opacity: 0.6, fontSize: 12 }}>
          trigger: <code>{JSON.stringify(r.trigger)}</code>
          {" — "}
          actions: <code>{JSON.stringify(r.actions)}</code>
        </div>
      </div>
      <div>
        <label>
          <input type="checkbox" checked={r.enabled} onChange={() => onToggle(r)} /> active
        </label>
        <button onClick={() => onDelete(r)}>Supprimer</button>
      </div>
    </div>
  );
}
