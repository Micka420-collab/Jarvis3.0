/** Helpers pour appeler /api/admin/* avec le token JWT en localStorage. */

const TOKEN_KEY = "jarvis.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string | null): void {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

async function call<T = any>(method: string, path: string, body?: any): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const tok = getToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const r = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401 || r.status === 403) {
    throw new Error("not_authorized");
  }
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status}: ${txt}`);
  }
  return r.json();
}

export const api = {
  login: (username: string) =>
    call<{ token: string; is_owner: boolean }>("POST", "/api/auth/login", { username }),

  // dashboard
  dashboard: () => call("GET", "/api/admin/dashboard"),

  // users
  listUsers: () => call("GET", "/api/admin/users"),
  createUser: (b: any) => call("POST", "/api/admin/users", b),
  patchUser: (id: string, b: any) => call("PATCH", `/api/admin/users/${id}`, b),
  deleteUser: (id: string) => call("DELETE", `/api/admin/users/${id}`),

  // devices
  listDevices: () => call("GET", "/api/admin/devices"),
  discoverHA: () => call("POST", "/api/admin/devices/discover/ha"),
  discoverZigbee: () => call("POST", "/api/admin/devices/discover/zigbee"),
  iotCommand: (b: any) => call("POST", "/api/iot/command", b),

  // routines
  listRoutines: () => call("GET", "/api/admin/routines"),
  toggleRoutine: (id: string, enabled: boolean) =>
    call("PATCH", `/api/admin/routines/${id}`, { enabled }),
  deleteRoutine: (id: string) => call("DELETE", `/api/admin/routines/${id}`),

  // skills
  listSkills: () => call("GET", "/api/admin/skills"),
  reloadSkills: () => call("POST", "/api/admin/skills/reload"),

  // agents
  listAgents: () => call("GET", "/api/admin/agents"),
  listAgentTasks: (limit = 50) =>
    call("GET", `/api/admin/agent-tasks?limit=${limit}`),
  delegate: (agent: string, goal: string) =>
    call("POST", "/api/admin/agent-delegate", { agent, goal }),

  // security
  securityStatus: () => call("GET", "/api/security/status"),
  silence: (minutes: number) =>
    call("POST", "/api/security/silence", { duration_minutes: minutes }),

  // traces
  listTraces: (limit = 50) => call("GET", `/api/admin/traces?limit=${limit}`),

  // presence
  getPresence: () => call("GET", "/api/admin/presence"),
  setPresence: (b: any) => call("POST", "/api/admin/presence", b),

  // push
  pushTest: (title: string, body: string) =>
    call("POST", "/api/admin/push-test", { title, body }),

  // wizard / connexions
  wizardState: () => call("GET", "/api/admin/wizard/state"),
  wizardTest: (b: any) => call("POST", "/api/admin/wizard/test", b),
};
