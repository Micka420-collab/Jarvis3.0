# Agents externes (Hermes, OpenClaw, MCP)

Jarvis peut **déléguer des tâches autonomes** à des agents qui interagissent avec ton PC : navigation web, fichiers, OS, GUI, services en ligne (Gmail, GitHub…). Tu parles à Jarvis, Jarvis pilote l'agent.

## Agents supportés

| Agent | Source | Forces |
|---|---|---|
| **Hermes Agent** | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | Auto-amélioration, mémoire persistante, 6 backends (local/Docker/SSH/Modal), 40+ tools, MCP natif, agents parallèles |
| **OpenClaw** | [openclaw.ai](https://openclaw.ai) | 50+ intégrations (Gmail, GitHub, Spotify, Obsidian, Twitter), skills marketplace, 100% local |
| **MCP générique** | n'importe quel serveur MCP | Custom tools |
| **Mock** | builtin | Tests offline |

## Architecture

```
              ┌─────────────────────────────────────────┐
   "Jarvis,   │     Orchestrator (skill agents)         │
    Hermes,   │       tool: agent_delegate              │
    fais X" ──▶                                          │
              └────────────────┬────────────────────────┘
                               │ HTTP /delegate
                               ▼
              ┌─────────────────────────────────────────┐
              │    Service `agents` (FastAPI :8005)     │
              │  - TaskRegistry (Postgres)              │
              │  - CLIAdapter / MCPAdapter / MockAdapter │
              │  - SSE stream output via /tasks/{id}    │
              └────────────────┬────────────────────────┘
                               │ subprocess / MCP stdio
                               ▼
              ┌──────────────┐  ┌──────────────┐
              │ hermes (CLI) │  │ openclaw     │
              │ + tools/MCP  │  │ + tools/MCP  │
              └──────────────┘  └──────────────┘
```

## Installation

Deux modes au choix.

### Mode A — Agents dans l'image Docker (par défaut OFF)

Inclut Hermes + OpenClaw dans l'image `jarvis-agents`. Image plus lourde (~1 Go), tout reste containerisé.

```bash
# build avec les agents préinstallés
make build-agents-full
docker compose up -d agents
```

L'image contient les deux binaires Hermes et OpenClaw, prêts à être pilotés via `subprocess`.

### Mode B — Agents installés sur l'host

Mode recommandé si tu veux que les agents accèdent à ton **vrai navigateur, ton vrai filesystem, ta vraie session GUI**. Le service `agents` reste dans Docker mais appelle les binaires sur l'hôte via une socket Docker partagée ou des volumes.

```bash
# 1) Sur l'host
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
curl -fsSL https://openclaw.ai/install.sh | bash

# 2) Dans Jarvis : pointe vers les binaires de l'hôte via volume
# docker-compose.override.yml :
services:
  agents:
    volumes:
      - /home/${USER}:/home/owner:rw
      - /usr/local/bin/hermes:/usr/local/bin/hermes:ro
      - /usr/local/bin/openclaw:/usr/local/bin/openclaw:ro
    environment:
      AGENT_HERMES_CMD: hermes
      AGENT_OPENCLAW_CMD: "openclaw chat -"
```

> **Sécurité** : monter `/home` rend tes fichiers personnels accessibles au container. Limite à un sous-dossier (`~/jarvis-workspace`) si possible.

### Mode C — Agents en SSH sur une autre machine

Si tu veux lancer les agents sur ton poste de bureau pendant que Jarvis tourne sur un Pi/serveur :

```env
AGENT_HERMES_CMD=ssh -T mickael@desktop.local hermes
AGENT_OPENCLAW_CMD=ssh -T mickael@desktop.local 'openclaw chat -'
```

Configurer une clé SSH sans passphrase pour le user du container `agents`.

## Configuration

Toutes via `.env` (voir `.env.example`) :

| Variable | Défaut | Effet |
|---|---|---|
| `INSTALL_HERMES` | `false` | Si `true` au build, image inclut Hermes |
| `INSTALL_OPENCLAW` | `false` | Idem pour OpenClaw |
| `AGENT_HERMES_CMD` | `hermes` | Commande shell complète (`shlex` parsed) |
| `AGENT_HERMES_TIMEOUT_S` | `600` | Tue le subprocess après ce délai |
| `AGENT_OPENCLAW_CMD` | `openclaw chat -` | Le `-` final force lecture stdin |
| `AGENT_*_MCP` | vide | Active le transport MCP au lieu du CLI |
| `AGENTS_ENABLE_MOCK` | `true` | Adapter mock pour tests offline |

## Utilisation depuis Jarvis

### Voix

> « Jarvis, demande à Hermes de classer mes téléchargements par type. »

Le LLM appelle `agent_delegate(agent="hermes", goal="classer les téléchargements par type dans ~/Téléchargements")`. Comme `requires_admin=True`, ta voix-print doit être validée (ou challenge phrase).

### REST direct

```bash
# Liste des agents dispo
curl https://jarvis.local/api/admin/skills/agents      # tools listés via /skills

# Délégation manuelle
curl -X POST http://localhost:8005/delegate \
  -H "Content-Type: application/json" \
  -d '{"agent":"hermes","goal":"liste les fichiers du bureau","user_id":null}'

# Suivi
curl http://localhost:8005/tasks/<task_id>
curl http://localhost:8005/tasks/<task_id>/stream    # SSE live output
```

### MCP

Si tu préfères MCP :

```env
AGENT_HERMES_MCP=hermes-mcp-server
```

Le service `agents` instancie alors un `MCPAdapter` qui parle le protocole stdio MCP. Les tools du serveur MCP de Hermes deviennent visibles via `agent_list` et automatiquement rappelables.

## Sécurité

Ces agents sont **puissants et délégués** : ils peuvent ouvrir ton navigateur, lire des fichiers, envoyer des e-mails. Précautions :

1. **Voix-print obligatoire** : le tool `agent_delegate` est `requires_admin=true`. Aucune action sans ta voix.
2. **Cooldown 30 s** : impossible de chaîner 50 délégations rapides.
3. **Audit** : chaque tâche est loggée dans `agent_tasks` (Postgres) avec user_id, agent, goal, output complet.
4. **Trace** : « Pourquoi Jarvis a-t-il fait ça ? » → `reasoning_traces` montre le tool call.
5. **Sandbox recommandé** : configure Hermes/OpenClaw avec leurs backends Docker/Modal pour isoler les exécutions risquées.

## Exemples concrets

```text
"Hermes, regarde mes mails et résume les non-lus depuis ce matin."
"OpenClaw, met à jour mon repo perso 'jarvis-skills' avec mes derniers commits locaux."
"Hermes, ouvre Chrome et compare les prix d'un MacBook Air M3 13'' chez Apple, Amazon, Boulanger."
"OpenClaw, trie mes téléchargements PDF dans Obsidian par tag automatique."
```

## Limitations connues

- **Hermes interactif par défaut** : si la sortie attend une question utilisateur, le subprocess bloque. Les nouveaux flags non-interactifs (`--print`, `--once`) sont à valider selon la version installée.
- **OpenClaw a un mode chat** : la commande `openclaw chat -` accepte un prompt unique sur stdin et termine après une réponse.
- **Pas de retour audio par défaut** : Jarvis te lit le résumé final via TTS quand la tâche est `completed`.
- **Authentification cloud** : la 1re exécution Hermes/OpenClaw demande de configurer les API keys (OpenAI, Anthropic). Le faire interactivement une fois (`docker compose exec agents hermes setup`) ou monter le fichier de config en volume.
