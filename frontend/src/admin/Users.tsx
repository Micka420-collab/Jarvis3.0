import { useEffect, useState } from "react";
import { api } from "./api";

const ROLES = ["owner", "adult", "teen", "child", "guest"] as const;

export function Users() {
  const [users, setUsers] = useState<any[]>([]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState<any>({ username: "", display_name: "", role: "adult", is_owner: false });
  const [err, setErr] = useState("");

  const reload = () => api.listUsers().then(setUsers).catch((e) => setErr(e.message));

  useEffect(() => {
    reload();
  }, []);

  const create = async () => {
    setErr("");
    try {
      await api.createUser(form);
      setShow(false);
      setForm({ username: "", display_name: "", role: "adult", is_owner: false });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const setRole = async (u: any, role: string) => {
    await api.patchUser(u.id, { role });
    reload();
  };

  const remove = async (u: any) => {
    if (!confirm(`Supprimer ${u.username} ?`)) return;
    await api.deleteUser(u.id);
    reload();
  };

  return (
    <div>
      <div className="row-actions">
        <h2>Membres ({users.length})</h2>
        <button onClick={() => setShow(true)}>+ Ajouter un membre</button>
      </div>

      {show && (
        <div className="modal">
          <h3>Nouveau membre</h3>
          <input
            placeholder="Username (sans espaces)"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <input
            placeholder="Nom complet"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {ROLES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
          <label>
            <input
              type="checkbox"
              checked={form.is_owner}
              onChange={(e) => setForm({ ...form, is_owner: e.target.checked })}
            />{" "}
            Owner
          </label>
          <div className="modal-actions">
            <button onClick={create}>Créer</button>
            <button onClick={() => setShow(false)}>Annuler</button>
          </div>
        </div>
      )}

      {err && <div className="error">{err}</div>}

      <table className="grid">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Rôle</th>
            <th>Voix</th>
            <th>Visage</th>
            <th>Owner</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>
                <strong>{u.display_name || u.username}</strong>
                <div style={{ opacity: 0.6, fontSize: 12 }}>@{u.username}</div>
              </td>
              <td>
                <select value={u.role} onChange={(e) => setRole(u, e.target.value)}>
                  {ROLES.map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </td>
              <td>{u.voice_enrolled ? "✓" : "—"}</td>
              <td>{u.face_enrolled ? "✓" : "—"}</td>
              <td>{u.is_owner ? "✓" : ""}</td>
              <td>
                <button onClick={() => remove(u)}>Supprimer</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
