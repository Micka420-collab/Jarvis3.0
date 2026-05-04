import { useState } from "react";
import { Agents } from "./Agents";
import { Dashboard } from "./Dashboard";
import { Devices } from "./Devices";
import { Login } from "./Login";
import { Routines } from "./Routines";
import { Security } from "./Security";
import { Skills } from "./Skills";
import { Traces } from "./Traces";
import { Users } from "./Users";
import { getToken, setToken } from "./api";

type Tab = "dashboard" | "users" | "devices" | "routines" | "skills" | "agents" | "security" | "traces";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: "■" },
  { id: "users", label: "Membres", icon: "👤" },
  { id: "devices", label: "Devices", icon: "⚡" },
  { id: "routines", label: "Routines", icon: "🔁" },
  { id: "skills", label: "Skills", icon: "🧩" },
  { id: "agents", label: "Agents", icon: "🤖" },
  { id: "security", label: "Sécurité", icon: "🛡" },
  { id: "traces", label: "Traces", icon: "🔍" },
];

export function Admin() {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [tab, setTab] = useState<Tab>("dashboard");

  if (!authed) {
    return (
      <div className="admin-shell">
        <Login onLoggedIn={() => setAuthed(true)} />
      </div>
    );
  }

  const logout = () => {
    setToken(null);
    setAuthed(false);
  };

  return (
    <div className="admin-shell">
      <aside className="admin-nav">
        <div className="brand-mini">JARVIS · admin</div>
        {TABS.map((t) => (
          <button key={t.id} className={`navlink ${tab === t.id ? "on" : ""}`} onClick={() => setTab(t.id)}>
            <span className="ico">{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
        <button className="navlink" style={{ marginTop: "auto" }} onClick={logout}>
          ↩ Déconnexion
        </button>
        <a href="/" className="navlink">← Retour à l'app</a>
      </aside>
      <main className="admin-main">
        {tab === "dashboard" && <Dashboard />}
        {tab === "users" && <Users />}
        {tab === "devices" && <Devices />}
        {tab === "routines" && <Routines />}
        {tab === "skills" && <Skills />}
        {tab === "agents" && <Agents />}
        {tab === "security" && <Security />}
        {tab === "traces" && <Traces />}
      </main>
    </div>
  );
}
