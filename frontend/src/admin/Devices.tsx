import { useEffect, useState } from "react";
import { api } from "./api";

export function Devices() {
  const [devices, setDevices] = useState<any[]>([]);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const reload = () => api.listDevices().then(setDevices).catch((e) => setErr(e.message));
  useEffect(() => {
    reload();
  }, []);

  const discover = async (provider: "ha" | "zigbee") => {
    setBusy(provider);
    setErr("");
    try {
      await (provider === "ha" ? api.discoverHA() : api.discoverZigbee());
      reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy("");
    }
  };

  const cmd = async (d: any, action: string) => {
    try {
      await api.iotCommand({ device_id: d.id, action, params: {} });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  return (
    <div>
      <div className="row-actions">
        <h2>Devices IoT ({devices.length})</h2>
        <button disabled={busy === "ha"} onClick={() => discover("ha")}>
          {busy === "ha" ? "..." : "Découvrir Home Assistant"}
        </button>
        <button disabled={busy === "zigbee"} onClick={() => discover("zigbee")}>
          {busy === "zigbee" ? "..." : "Découvrir Zigbee2MQTT"}
        </button>
      </div>

      {err && <div className="error">{err}</div>}

      <table className="grid">
        <thead>
          <tr>
            <th>Nom</th>
            <th>ID</th>
            <th>Transport</th>
            <th>Admin</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((d) => (
            <tr key={d.id}>
              <td>{d.name}</td>
              <td>
                <code>{d.id}</code>
              </td>
              <td>
                <span className={`badge tr-${d.transport}`}>{d.transport}</span>
              </td>
              <td>{d.requires_admin ? "🔒" : ""}</td>
              <td>
                <button onClick={() => cmd(d, "on")}>on</button>
                <button onClick={() => cmd(d, "off")}>off</button>
                <button onClick={() => cmd(d, "toggle")}>toggle</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
