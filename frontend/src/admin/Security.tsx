import { useEffect, useState } from "react";
import { api } from "./api";

export function Security() {
  const [status, setStatus] = useState<any>(null);
  const [presence, setPresence] = useState<any>(null);
  const [err, setErr] = useState("");

  const reload = async () => {
    try {
      const [s, p] = await Promise.all([api.securityStatus(), api.getPresence()]);
      setStatus(s);
      setPresence(p);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    reload();
    const i = setInterval(reload, 5000);
    return () => clearInterval(i);
  }, []);

  const toggleAway = async () => {
    await api.setPresence({
      away: !presence?.away,
      simulate_presence: true,
    });
    reload();
  };

  const silence30 = async () => {
    await api.silence(30);
    reload();
  };

  const pushTest = async () => {
    try {
      const r: any = await api.pushTest("Jarvis", "Test depuis l'admin");
      alert(`Push envoyé: ${r.sent}, échecs: ${r.failed}`);
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div>
      <h2>Sécurité & Présence</h2>

      <div className="card">
        <h3>Argus (réseau)</h3>
        {status ? (
          <>
            <p>
              Statut :{" "}
              <span className={status.connected ? "badge tr-mqtt" : "badge tr-serial"}>
                {status.connected ? "connecté" : "déconnecté"}
              </span>
            </p>
            {status.silenced && (
              <p>
                🔕 Silenced encore {Math.round((status.silence_remaining_s || 0) / 60)} min
              </p>
            )}
            {status.last_alert && (
              <pre style={{ background: "rgba(0,0,0,0.3)", padding: 8, borderRadius: 4 }}>
                {JSON.stringify(status.last_alert, null, 2)}
              </pre>
            )}
            <button onClick={silence30}>Mute 30 min</button>
          </>
        ) : (
          <p>Chargement…</p>
        )}
      </div>

      <div className="card">
        <h3>Présence</h3>
        {presence ? (
          <>
            <p>
              Mode absence :{" "}
              <span className={presence.away ? "badge tr-zigbee2mqtt" : "badge"}>
                {presence.away ? "ABSENT" : "présent"}
              </span>
              {presence.simulate_presence && presence.away && " · simulation activée"}
            </p>
            <button onClick={toggleAway}>
              {presence.away ? "Marquer présent" : "Mode absence (simulation)"}
            </button>
          </>
        ) : (
          <p>Chargement…</p>
        )}
      </div>

      <div className="card">
        <h3>Notifications push</h3>
        <button onClick={pushTest}>Envoyer un push de test</button>
      </div>

      {err && <div className="error">{err}</div>}
    </div>
  );
}
