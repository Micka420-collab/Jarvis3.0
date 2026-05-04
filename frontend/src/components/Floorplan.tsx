import { useEffect, useRef, useState } from "react";

type Room = { id: string; name: string; polygon: string; fill?: string };
type Device = { id: string; room: string; kind: string; x: number; y: number };
type Camera = { id: string; room: string; x: number; y: number; fov?: number; angle?: number };
type Plan = { viewBox: string; rooms: Room[]; devices: Device[]; cameras?: Camera[] };

type IotState = Record<string, { state?: string | number | boolean; on?: boolean }>;

const STATE_COLOR_ON = "#4cc9f0";
const STATE_COLOR_OFF = "#3a4a6a";

function deviceColor(kind: string, state?: { state?: any; on?: boolean }): string {
  if (state?.on || state?.state === "ON" || state?.state === "open" || state?.state === true) {
    return STATE_COLOR_ON;
  }
  return STATE_COLOR_OFF;
}

export function Floorplan() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [iot, setIot] = useState<IotState>({});
  const [presentRooms, setPresentRooms] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetch("/floorplan.example.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => setPlan(p))
      .catch(() => setPlan(null));
  }, []);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/avatar`);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.channel === "ui.iot") {
        const ev = msg.payload || {};
        const did = ev.device_id;
        if (did) setIot((s) => ({ ...s, [did]: { state: ev.state?.state, on: !!ev.state?.on } }));
      } else if (msg.channel === "ui.vision") {
        const ev = msg.payload || {};
        const room = ev.camera; // simpli : on utilise le nom de cam comme room
        if (!room) return;
        setPresentRooms((s) => {
          const n = new Set(s);
          n.add(room);
          // disparaît au bout de 30s
          setTimeout(() => setPresentRooms((s2) => {
            const n2 = new Set(s2);
            n2.delete(room);
            return n2;
          }), 30_000);
          return n;
        });
      }
    };
    return () => ws.close();
  }, []);

  if (!plan) {
    return (
      <div style={{ padding: 16, opacity: 0.6, fontSize: 13 }}>
        Aucun plan trouvé. Copie <code>floorplan.example.json</code> en{" "}
        <code>floorplan.json</code> et adapte-le à ta maison.
      </div>
    );
  }

  return (
    <svg viewBox={plan.viewBox} style={{ width: "100%", height: "100%" }}>
      {plan.rooms.map((r) => (
        <g key={r.id}>
          <polygon
            points={r.polygon}
            fill={presentRooms.has(r.id) ? "#1f3d6a" : r.fill || "#1a2540"}
            stroke="#4cc9f0"
            strokeWidth={presentRooms.has(r.id) ? 3 : 1}
            opacity={0.85}
          />
          <text
            x={r.polygon.split(" ")[0].split(",")[0]}
            y={Number(r.polygon.split(" ")[0].split(",")[1]) + 22}
            fontSize={14}
            fill="#d8e2f0"
            opacity={0.7}
            transform="translate(8, 0)"
          >
            {r.name}
          </text>
        </g>
      ))}
      {plan.devices.map((d) => (
        <g key={d.id} transform={`translate(${d.x}, ${d.y})`}>
          <circle r={10} fill={deviceColor(d.kind, iot[d.id])} stroke="#fff" strokeWidth={1} />
          <text fontSize={10} fill="#d8e2f0" y={-14} textAnchor="middle">
            {d.id.split(".").pop()}
          </text>
        </g>
      ))}
      {(plan.cameras || []).map((c) => (
        <g key={c.id} transform={`translate(${c.x}, ${c.y})`}>
          <polygon
            points={`0,0 ${(c.fov || 60) * 0.6},-${(c.fov || 60) * 0.4} ${(c.fov || 60) * 0.6},${(c.fov || 60) * 0.4}`}
            fill="#4cc9f0"
            opacity={0.15}
            transform={`rotate(${c.angle || 0})`}
          />
          <circle r={6} fill="#f72585" />
        </g>
      ))}
    </svg>
  );
}
