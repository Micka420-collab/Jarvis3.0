import { useState } from "react";
import { api, setToken } from "./api";

export function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const r = await api.login(username);
      if (!r.is_owner) {
        setError("Cet utilisateur n'est pas owner. Seul l'owner accède à l'admin.");
        return;
      }
      setToken(r.token);
      onLoggedIn();
    } catch (e: any) {
      setError(`Erreur : ${e.message}`);
    }
  };

  return (
    <div className="login">
      <h1>Admin Jarvis</h1>
      <p style={{ opacity: 0.7, fontSize: 13 }}>
        Entre ton nom d'utilisateur owner pour obtenir un token JWT et accéder à la console.
      </p>
      <form onSubmit={submit}>
        <input
          autoFocus
          placeholder="Username (ex: mickael)"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <button type="submit">Se connecter</button>
      </form>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
