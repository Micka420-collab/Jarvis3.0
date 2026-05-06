<div align="center">

# Jarvis 3.0

**Assistant domotique auto-hébergé pour réseau local.**
Voix, vision, mémoire, IoT et sécurité réseau — sur ton serveur, sous ton contrôle.

[![Status](https://img.shields.io/badge/status-active-22c55e?style=flat-square)](#)
[![License](https://img.shields.io/badge/license-MIT-3b82f6?style=flat-square)](#licence)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%C2%B7%20React%20%C2%B7%20Three.js-1f2937?style=flat-square)](#stack-technique)
[![Deploy](https://img.shields.io/badge/deploy-Compose%20%7C%20k3s%20%7C%20Pi%20ARM64-2563eb?style=flat-square)](#plateformes-de-déploiement)
[![PWA](https://img.shields.io/badge/PWA-installable-7c3aed?style=flat-square)](#mobile--pwa)
[![Argus](https://img.shields.io/badge/integrates-Argus%20SOC-ef4444?style=flat-square)](https://github.com/Micka420-collab/Argus)

[Fonctionnalités](#fonctionnalités) ·
[Architecture](#architecture) ·
[Installation](#installation) ·
[Stack](#stack-technique) ·
[Phases](#phases-de-livraison) ·
[Plateformes](#plateformes-de-déploiement) ·
[Sécurité](#sécurité) ·
[Documentation](docs/)

</div>

---

## Vision

Jarvis 3.0 est un assistant inspiré du **J.A.R.V.I.S. d'Iron Man**, conçu pour être :

- **Local-first** — aucune donnée ne quitte ton réseau par défaut.
- **Modulaire** — chaque capacité (voix, vision, mémoire, IoT, sécurité) vit dans son propre service Docker.
- **Provider-agnostic** — l'IA tourne en local (Ollama + Whisper + Piper) ou bascule sur le cloud (Claude, Mistral, ElevenLabs) sans toucher au code.
- **Intégré à ton SOC** — branché à [Argus](https://github.com/Micka420-collab/Argus) pour annoncer vocalement les menaces réseau (Wazuh + Suricata + OpenSearch).

---

## Fonctionnalités

| Domaine | Capacités |
|---|---|
| **Voix** | Wake-word, STT streaming partials, VAD silero, **conversation duplex avec barge-in** (interruption), TTS streaming `Piper`/`ElevenLabs` |
| **Avatar** | React + Three.js, **GLTF haute-fidélité avec 52 blendshapes ARKit** (fallback icosaèdre), idle motion + clignement, waveform live |
| **LLM** | Routeur multi-provider Ollama / Claude / Mistral · **streaming token → phrase-par-phrase → TTS** (latence perçue <500 ms) · tool calling |
| **Skills** | Système de **plugins hot-reload** (POST `/skills/reload`) · 7 builtins : time, weather, briefing, routines, presence, explain, **agents** |
| **Agents externes** | Délégation à **Hermes Agent** (Nous Research) et **OpenClaw** : navigation, fichiers, OS, GUI, 50+ services en ligne. Voix-print obligatoire. |
| **Mémoire** | Vectorielle (`Qdrant` + bge-m3) + faits structurés (`Postgres pgvector`) |
| **Profils familiaux** | Multi-utilisateurs avec rôles (owner/adult/teen/child/guest), permissions JSON, voix-print et visage par membre |
| **Voix-print** | ECAPA-TDNN 192-d, **multi-membres**, challenge phrase dynamique, **liveness AASIST anti-deepfake**, cooldown admin |
| **Briefing matinal** | Météo (Open-Meteo) + agenda CalDAV + état Argus + état IoT en un tool LLM |
| **Routines apprises** | Service `learning` détecte les patterns (`device × heure × ≥N jours`) et propose des automations à l'owner |
| **Présence simulée** | Mode anti-cambriolage : rejoue les actions IoT typiques avec randomisation pendant l'absence |
| **IoT** | MQTT (Mosquitto) · Home Assistant (REST + discovery) · Arduino USB série · **Zigbee2MQTT** (avec discovery + states) |
| **Vision** | Frigate (NVR/RTSP) + InsightFace (reconnaissance faciale multi-visages) |
| **Sécurité** | Client WS Argus · mapping MITRE ATT&CK FR · alertes vocales proactives |
| **Vue maison 2D** | Floorplan SVG temps réel : pièces, devices, caméras, occupation détectée |
| **Explainability** | Trace de raisonnement persistée + bouton « Pourquoi ? » dans l'UI + endpoint `/api/explain/last` |
| **Bus** | Redis Streams (durable + replay) + pub/sub UI temps réel |
| **Mobile** | PWA installable + **Web Push notifications natives** (VAPID + service worker) |

---

## Architecture

```
                         ┌──────────────────────────────────────────┐
                         │  React + Vite + Three.js   (avatar 3D)   │
                         │  AudioWorklet capture · PCM streaming    │
                         └──────────────────┬───────────────────────┘
                                            │  HTTPS / WSS  (JWT)
                                            ▼
                         ┌──────────────────────────────────────────┐
                         │             Gateway  (FastAPI)            │
                         │  Auth · REST /api · WS /ws/voice /ws/avatar │
                         └──────────────────┬───────────────────────┘
                                            │
   ┌────────────┬────────────┬──────────────┼──────────────┬────────────┬────────────┐
   ▼            ▼            ▼              ▼              ▼            ▼            ▼
┌──────┐    ┌──────┐    ┌────────────┐  ┌────────┐    ┌──────┐    ┌──────────┐  ┌──────────┐
│voice │    │ llm  │    │orchestrator│  │ memory │    │ iot  │    │ security │  │  vision  │
│ STT  │    │router│    │tool calling│  │Qdrant +│    │MQTT +│    │client WS │  │Frigate + │
│ TTS  │    │      │    │   gating   │  │ facts  │    │HA/USB│    │  Argus   │  │InsightFace│
│ VP   │    │      │    │ challenge  │  │        │    │      │    │  MITRE   │  │          │
└──────┘    └──────┘    └────────────┘  └────────┘    └──────┘    └──────────┘  └──────────┘
   │            │            │              │              │            │            │
   └────────────┴────────────┴───── Redis Streams + pub/sub ─────────────┴────────────┘
                                            │
   ┌────────────────────────────────────────┴─────────────────────────────────────┐
   │  Qdrant   ·   Postgres + pgvector   ·   Mosquitto   ·   Ollama   ·   Traefik │
   └──────────────────────────────────────────────────────────────────────────────┘
                                            │
   ┌────────────────────────────────────────┴─────────────────────────────────────┐
   │     Externes : Home Assistant   ·   Argus SOC   ·   Frigate cams   ·   Arduino USB
   └──────────────────────────────────────────────────────────────────────────────┘
```

Détails et choix techniques : [`docs/architecture.md`](docs/architecture.md).

---

## Installation

### Prérequis

- Docker Engine 24+ et Docker Compose v2
- 8 Go RAM mini · 16 Go recommandé pour le LLM local
- (optionnel) GPU NVIDIA pour Whisper float16 + vision CUDA
- (optionnel) [Argus](https://github.com/Micka420-collab/Argus) déployé pour les alertes réseau

### Installation en une commande

**Ubuntu / Debian (auto-installe Docker)** :
```bash
curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Jarvis3.0/main/install-ubuntu.sh | bash
```

**Autres distros / macOS** (Docker doit être déjà installé) :
```bash
curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Jarvis3.0/main/install.sh | bash
```

Le script :
- détecte ton OS et ton archi (Linux/macOS · amd64/arm64)
- vérifie Docker (et propose de l'installer si absent)
- clone (ou met à jour) le dépôt dans `~/Jarvis3.0`
- génère des secrets aléatoires sécurisés (JWT, Postgres, MQTT, **clés VAPID** pour les push)
- crée le réseau Docker partagé avec Argus
- télécharge les modèles Piper, build et lance la stack
- **lance le wizard interactif** qui te connecte chaque feature à l'IA (LLM, Home Assistant, Zigbee, Z-Wave, Frigate, Argus, agents, voix-print)
- imprime ton URL d'accès

Pour relancer le wizard plus tard : `cd ~/Jarvis3.0 && make wizard`. Tu peux aussi tester chaque connexion en live depuis **`/admin → Connexions`**.

📘 **Guide d'intégration détaillé** : [`docs/integrations.md`](docs/integrations.md) explique chaque section (LLM, Home Assistant, Zigbee, Z-Wave, Frigate, Argus, push, multi-room, agents, voix-print) avec prérequis, credentials, vars `.env`, tests et erreurs fréquentes.

Une fois terminé : ouvre **`https://jarvis.local`** (assistant) ou **`https://jarvis.local/admin`** (console).

### Installation manuelle (avancée)

```bash
git clone https://github.com/Micka420-collab/Jarvis3.0.git && cd Jarvis3.0
cp .env.example .env && $EDITOR .env       # règle les secrets
docker network create proxmox_lan
make download-models
make up                                     # ou : make up-gpu / make up-vision / make up-rpi
bash scripts/healthcheck.sh
```

### Commandes utiles

| Commande | Action |
|---|---|
| `make up` | Lance gateway, voice, llm, memory, orchestrator, iot, security, vision, frontend |
| `make up-gpu` | Override CUDA pour Whisper float16 et InsightFace |
| `make up-vision` | Active Frigate (profile `vision`) |
| `make logs s=voice` | Suit les logs d'un service |
| `make enroll-voice` | Enrôle ta voix (5 phrases, ~30 s) |
| `make enroll-face name=mickael image=./photo.jpg` | Enrôle un visage |
| `make discover-ha` | Synchronise les entités Home Assistant en BDD |
| `make test` / `make e2e` | Tests unitaires / end-to-end |

---

## Stack technique

| Couche | Technologies |
|---|---|
| **Frontend** | React 18 · Vite · TypeScript · Three.js · @react-three/fiber · AudioWorklet |
| **Gateway** | FastAPI · Uvicorn · PyJWT · asyncpg · Traefik (reverse proxy + TLS) |
| **Voix** | faster-whisper · Piper · ElevenLabs · openWakeWord · silero-vad · SpeechBrain ECAPA-TDNN |
| **LLM** | Adapter Ollama · Anthropic Claude · Mistral (router maison, schéma Anthropic) |
| **Mémoire** | Qdrant 1.11 · sentence-transformers (bge-m3) · Postgres 16 + pgvector |
| **IoT** | asyncio-mqtt (Mosquitto 2) · httpx (Home Assistant REST) · pyserial-asyncio (Arduino) |
| **Vision** | Frigate · InsightFace (buffalo_l) · OpenCV · ONNX Runtime |
| **Sécurité** | websockets (client Argus) · mapping MITRE ATT&CK FR |
| **Bus** | Redis Streams (durable, consumer groups) + pub/sub volatile UI |
| **Orchestration** | Docker Compose v2 · profile `vision` · override `gpu` |
| **Tests** | pytest · pytest-asyncio · httpx · websockets · ruff |

---

## Phases de livraison

| Phase | Contenu | Statut |
|:-:|---|:-:|
| **0** | Squelette infra · gateway · frontend · TLS · Postgres + pgvector | `done` |
| **1** | Voix bidir · STT/TTS streaming · VAD silero · LLM hybride · avatar 3D + visèmes | `done` |
| **2** | Mémoire vectorielle · voix-print créateur · challenge phrase · gating admin | `done` |
| **3** | Client Argus WS · mapping MITRE ATT&CK FR · TTS proactif · silence voix-print | `done` |
| **4** | IoT MQTT + Home Assistant + Arduino USB · HA discovery · firmware exemple | `done` |
| **5** | Frigate + InsightFace · enroll webcam · TTS contextuelle | `done` |

Détail par phase et tests E2E : [`docs/phases.md`](docs/phases.md).

---

## Structure du dépôt

```
Jarvis3.0/
├── docker-compose.yml           orchestration globale
├── docker-compose.gpu.yml       override CUDA
├── Makefile                     up · logs · tests · enroll-{voice,face} · discover-ha
├── .env.example                 secrets et variables d'environnement
│
├── infra/
│   ├── traefik/                 reverse proxy + TLS LAN
│   ├── mosquitto/               broker MQTT + ACL
│   ├── postgres/init.sql        schéma : users · voiceprints · auth_events · devices · facts
│   ├── qdrant/                  stockage vectoriel
│   └── frigate/config.yml       caméras RTSP (profile vision)
│
├── services/
│   ├── _shared/                 schémas Pydantic du bus + client Redis Streams
│   ├── gateway/                 FastAPI · auth · routes · WS voice/avatar
│   ├── voice/                   STT · TTS · VAD · wake-word · voix-print · visèmes
│   ├── llm/                     router + adapters Ollama / Claude / Mistral
│   ├── orchestrator/            tool calling · IdentityStore · challenge phrase
│   ├── memory/                  Qdrant + embedder + facts
│   ├── iot/                     MQTT + HA + serial bridges + devices.yaml
│   ├── security/                client WS Argus + alert mapper MITRE
│   └── vision/                  Frigate consumer + InsightFace
│
├── frontend/
│   └── src/                     App · Avatar3D · Waveform · useVoiceWS · audio.ts
│
├── examples/arduino/            firmware exemple (porte de garage JSON-line)
├── scripts/                     download_models · enroll_voiceprint · enroll_face · healthcheck
├── tests/                       unit (challenge, identity, mapper, events) + e2e (health, voice)
├── models/                      téléchargés au runtime (gitignored)
├── k8s/                         manifests Kubernetes/k3s (base + overlays prod & rpi)
└── docs/                        architecture · voiceprint · phases · k3s · raspberry-pi · avatar-gltf
```

---

## Plateformes de déploiement

Trois cibles supportées avec la même base de code :

| Cible | Commande | Ressources mini |
|---|---|---|
| **Docker Compose** sur Proxmox / serveur Linux | `make up` | 8 Go RAM · x86_64 |
| **Kubernetes (k3s)** mono ou multi-nœud | `kubectl apply -k k8s/overlays/prod` | k3s installé · cluster ≥ 1 nœud |
| **Raspberry Pi 4 / 5** (ARM64) | `make up-rpi` | Pi 4 (4 Go) ou Pi 5 (8 Go) |

Les images Docker sont buildées multi-arch (`linux/amd64` + `linux/arm64`) avec `make build-multiarch`.

Détails :
- [`docs/k3s.md`](docs/k3s.md) — manifests Kustomize, secrets, TLS, scaling
- [`docs/raspberry-pi.md`](docs/raspberry-pi.md) — overrides ARM64, périphériques USB, perfs

### Mobile / PWA

Le frontend est une **PWA installable** :
- Sur Android : "Ajouter à l'écran d'accueil" → app standalone avec icône
- Sur iOS : "Sur l'écran d'accueil" → comportement quasi-natif
- Service worker met en cache l'avatar GLTF et les assets, offline-friendly
- Pas de cache des appels `/api` ni `/ws` (toujours réseau)

---

## Sécurité

| Mécanisme | Description | Fichier clé |
|---|---|---|
| **Authentification web** | JWT signé HMAC, expiration configurable | `services/gateway/app/auth.py` |
| **Voix-print créateur** | ECAPA-TDNN 192-d en pgvector, similarité cosine, seuils configurables | `services/voice/app/voiceprint.py` |
| **Anti-replay vocal** | Challenge phrase dynamique 3 mots, TTL 30 s | `services/orchestrator/app/challenge.py` |
| **Cooldown admin** | 1 commande sensible / 30 s par utilisateur | `services/gateway/app/auth.py` |
| **TLS LAN** | Traefik avec cert auto pour `jarvis.local` | `infra/traefik/traefik.yml` |
| **Isolation réseau** | Pas de bind public hors gateway · réseau dédié + `proxmox_lan` partagé Argus | `docker-compose.yml` |
| **Audit** | Table `auth_events` (Postgres) sur chaque vérif voix et commande admin | `infra/postgres/init.sql` |

Détail du modèle voix-print : [`docs/voiceprint.md`](docs/voiceprint.md).

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — schéma complet, choix techniques, contrats inter-services
- [`docs/voiceprint.md`](docs/voiceprint.md) — modèle ECAPA, enrôlement, anti-deepfake AASIST
- [`docs/avatar-gltf.md`](docs/avatar-gltf.md) — formats GLTF, blendshapes ARKit, sources
- [`docs/phases.md`](docs/phases.md) — détail livraison par phase + tests E2E
- [`docs/k3s.md`](docs/k3s.md) — déploiement Kubernetes / k3s
- [`docs/raspberry-pi.md`](docs/raspberry-pi.md) — installation et perfs sur Pi 4 / Pi 5
- [`docs/skills.md`](docs/skills.md) — anatomie d'un plugin et hot-reload
- [`docs/agents.md`](docs/agents.md) — délégation à Hermes / OpenClaw / MCP
- [`docs/integrations.md`](docs/integrations.md) — guide complet d'intégration de chaque feature
- [`docs/operations.md`](docs/operations.md) — backup, monitoring, rate limiting, fail2ban
- [`docs/federation.md`](docs/federation.md) — fédération multi-instances (résidence principale ↔ secondaire)

---

## Avancées et roadmap

### Récemment livré

- **Délégation à des agents autonomes** : Hermes (NousResearch) + OpenClaw + MCP générique. Jarvis peut leur confier des tâches PC réelles (browser, fichiers, GUI, services en ligne).
- **Profils utilisateurs familiaux** multi-membres (rôles, permissions, voix-print et visage par membre)
- **Skills system** extensible avec hot-reload (5 builtins : time, weather, briefing, routines, presence, explain)
- **LLM streaming → TTS phrase-par-phrase** (chunker FR + abréviations, latence perçue <500 ms)
- **Conversation duplex avec barge-in** : couper Jarvis pendant qu'il parle
- **Briefing matinal intelligent** : météo Open-Meteo + agenda CalDAV + état SOC + IoT
- **Routines apprises automatiquement** : pattern detection sur observations IoT, propose à l'owner
- **Mode présence simulée** anti-cambriolage : rejoue actions typiques avec randomisation
- **Web Push notifications PWA** : VAPID + service worker + UI subscribe
- **Vue maison 2D** : floorplan SVG temps réel (pièces, devices, caméras, occupation)
- **Explainability** : trace de raisonnement persistée + bouton « Pourquoi ? » dans l'UI
- Avatar GLTF haute-fidélité avec 52 blendshapes ARKit + lerp 30 ms + clignement
- Liveness AASIST anti-deepfake (gating commandes admin)
- Zigbee2MQTT (commandes + discovery + states sur le bus)
- Manifests Kubernetes/k3s (Kustomize base + overlays prod / rpi)
- Build multi-arch (amd64 + arm64) + override Raspberry Pi

### Récemment livré (suite)

- **Helm chart Kubernetes** : `helm install jarvis ./helm/jarvis` + `values.rpi.yaml` pour ARM64
- **Memory-augmented prompting** : top-K souvenirs Qdrant injectés en contexte à chaque tour (RAG)
- **Z-Wave natif** via zwave-js-ui (parallèle à Zigbee2MQTT) — discovery + commandes MQTT
- **App native Capacitor** : iOS + Android, push notifs, splash (`npm run cap:add:android`)
- **Multimodal Claude Vision** : provider `anthropic-vision` injecte une frame Frigate dans le prompt
- **Multi-room audio** : `SpeakerRouter` + mapping caméra→pièce, mise à jour automatique via les events `vision.face.recognized`
- **Mode agent autonome** : `is_autonomous_request()` détecte les goals complexes et chaîne jusqu'à 8 tool calls
- **OpenRouter** : provider gateway-unifié (200+ modèles via une seule clé)
- **Wizard interactif** : `make wizard` — connecte LLM, HA, Zigbee, Z-Wave, Frigate, Argus, agents, voix
- **Console admin web** : 9 onglets dont Routine Builder visuel
- **CI GitHub Actions** : lint Python/shell/YAML + tests pytest + smoke build Docker + frontend build
- **Backup / restore** : Postgres + Qdrant + Redis + configs en tarball, retention + rsync remote
- **Stack monitoring** : Prometheus + Grafana + Loki + Promtail + cAdvisor + Node Exporter (`make monitoring-up`)
- **Rate limiting Traefik** : 60 req/s + HSTS + frame-deny + fail2ban
- **Détection deepfake** : `DeepfakeDetector` (MiniFASNet ONNX + fallback heuristique temporel)
- **Fédération multi-instances** : service `federation` avec heartbeat HTTP entre peers

### À venir

- Tests E2E avec mock devices (HA simulé, MQTT testcontainer)
- Catalog sync fédération v0.2 (devices/routines/users)
- mTLS entre instances fédérées

---

## Licence

MIT — voir [LICENSE](LICENSE).
Inspiré par J.A.R.V.I.S. (Iron Man, Marvel) à des fins purement personnelles et techniques.

---

<div align="center">

**Construit avec [Claude Code](https://claude.ai/code)** · Auto-hébergé sur Proxmox · Compatible avec [Argus SOC](https://github.com/Micka420-collab/Argus)

</div>
