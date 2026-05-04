# Jarvis 3.0

Assistant domotique auto-hébergé inspiré de **Jarvis (Iron Man)**, déployable sur **Proxmox** aux côtés de [Argus](https://github.com/Micka420-collab/Argus) (sécurité réseau).

## Fonctionnalités cibles

- **Interface web avatar 3D** parlant (lipsync via visèmes)
- **Voix bidirectionnelle** : wake-word → STT → LLM → TTS, latence cible <2 s
- **Authentification biométrique vocale** (voix-print ECAPA-TDNN) : seul le créateur déclenche les commandes admin
- **Mémoire long-terme** vectorielle (Qdrant)
- **IoT multi-protocole** : MQTT (ESP32/ESPHome), Home Assistant, Arduino USB série
- **Sécurité réseau** : alertes Argus poussées vocalement
- **Vision** : reconnaissance faciale via Frigate + InsightFace
- **IA hybride** : provider swappable (Ollama local / Claude API / Mistral / ElevenLabs / Piper)

## Architecture

Mono-repo Docker Compose, services modulaires reliés par un bus Redis Streams :

```
React+Three.js (avatar) ─ HTTPS/WSS ─ FastAPI gateway
                                      │
            ┌──────────┬──────────┬───┴───┬──────────┬──────────┐
          voice      llm     orchestrator memory   iot/security  vision
            │         │          │          │          │          │
            └─────────┴──── Redis Streams ──┴──────────┴──────────┘
                                  │
   Qdrant │ Postgres+pgvector │ Mosquitto │ Ollama │ Frigate
            externes : Home Assistant │ Argus │ Arduino USB
```

Détails complets : [docs/architecture.md](docs/architecture.md).

## Démarrage rapide

```bash
# 1. Préparer l'environnement
cp .env.example .env
# éditer .env (au minimum JWT_SECRET, POSTGRES_PASSWORD, OWNER_USERNAME)

# 2. Créer le réseau partagé avec Argus (optionnel)
docker network create proxmox_lan

# 3. Télécharger les modèles (Whisper, Piper, ECAPA, avatar GLTF)
make download-models

# 4. Lancer la stack
make up

# 5. Vérifier
curl -k https://jarvis.local/api/health
```

UI : `https://jarvis.local`

## Phases de livraison

| Phase | Contenu | État |
|---|---|---|
| 0 | Squelette infra + gateway + frontend placeholder | ✅ |
| 1 | Voix bidir + LLM hybride + avatar 3D | 🚧 squelette posé |
| 2 | Mémoire long-terme + voix-print créateur | 🚧 squelette posé |
| 3 | Intégration Argus (alertes vocales) | 🚧 squelette posé |
| 4 | IoT MQTT + HA + Arduino série | 🚧 squelette posé |
| 5 | Vision (caméra + reconnaissance faciale) | 🚧 squelette posé |

Voir [docs/phases.md](docs/phases.md) pour le détail.

## Structure

```
Jarvis3.0/
├── docker-compose.yml           # orchestration
├── docker-compose.gpu.yml       # override CUDA
├── Makefile                     # raccourcis dev
├── infra/                       # configs Mosquitto, Postgres, Traefik
├── services/                    # microservices Python (gateway, voice, llm, …)
│   └── _shared/events.py        # schémas Pydantic du bus
├── frontend/                    # React + Vite + Three.js
├── models/                      # gitignored (téléchargés)
├── scripts/                     # utilitaires (enroll voix-print, download)
├── tests/                       # pytest unit + e2e
└── docs/                        # architecture, voiceprint, phases
```

## Sécurité

- Auth JWT (`services/gateway/app/auth.py`)
- Voix-print ECAPA + challenge phrase + cooldown admin (voir [docs/voiceprint.md](docs/voiceprint.md))
- TLS LAN via Traefik
- Pas de bind 0.0.0.0 hors gateway

## Licence

MIT.
