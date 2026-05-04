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
| **Voix** | Wake-word (`openWakeWord`), STT (`faster-whisper`), VAD silero, **partial transcripts streaming**, TTS streaming (`Piper` / `ElevenLabs`) |
| **Avatar** | React + Three.js, **GLTF haute-fidélité avec 52 blendshapes ARKit** (fallback icosaèdre), waveform live |
| **LLM** | Routeur multi-provider : Ollama (local) · Claude · Mistral · prompt système & tool calling |
| **Mémoire** | Vectorielle (`Qdrant` + bge-m3) + faits structurés (`Postgres pgvector`) |
| **Voix-print** | Biométrie ECAPA-TDNN 192-d · challenge phrase dynamique · **liveness AASIST anti-deepfake** · cooldown admin |
| **IoT** | MQTT (Mosquitto) · Home Assistant (REST + discovery) · Arduino USB série (JSON-line) · **Zigbee2MQTT** |
| **Vision** | Frigate (NVR/RTSP) + InsightFace (reconnaissance faciale) + enroll webcam |
| **Sécurité** | Client WS Argus · mapping MITRE ATT&CK · alertes vocales proactives · liveness anti-spoof |
| **Bus** | Redis Streams (durable + replay) + pub/sub UI temps réel |
| **Mobile** | PWA installable (manifest + service worker + offline cache GLTF) |

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

### Quickstart (5 commandes)

```bash
# 1.  Cloner et configurer
git clone https://github.com/Micka420-collab/Jarvis3.0.git && cd Jarvis3.0
cp .env.example .env
$EDITOR .env                                 # JWT_SECRET, POSTGRES_PASSWORD, OWNER_USERNAME

# 2.  Réseau partagé avec Argus (si déployé)
docker network create proxmox_lan

# 3.  Modèles (Piper voix fr, Whisper auto-DL au 1er run)
make download-models

# 4.  Démarrer la stack
make up                                      # ou : make up-gpu / make up-vision

# 5.  Vérifier
bash scripts/healthcheck.sh
open https://jarvis.local
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

---

## Avancées et roadmap

### Récemment livré

- Avatar GLTF haute-fidélité avec 52 blendshapes ARKit + lerp 30 ms + clignement
- Streaming partial transcripts Whisper, affichés en gris dans l'UI (< 1 s)
- Liveness AASIST anti-deepfake (gating commandes admin)
- Zigbee2MQTT integré (commandes + discovery + states sur le bus)
- Frontend PWA installable (manifest, service worker, offline GLTF cache)
- Manifests Kubernetes/k3s (Kustomize base + overlays prod / rpi)
- Build multi-arch (amd64 + arm64) + override Raspberry Pi avec limites mémoire

### À venir

- Streaming token-par-token côté LLM → TTS (latence < 700 ms perçue)
- Déploiement automatisé via Helm chart (en alternative à Kustomize)
- Memory-augmented prompting : tirer automatiquement les `n` souvenirs les plus pertinents avant chaque tour
- Z-Wave natif via zwavejs2mqtt (en plus de Zigbee2MQTT)
- App native (Capacitor) pour intégration plus profonde Android/iOS

---

## Licence

MIT — voir [LICENSE](LICENSE).
Inspiré par J.A.R.V.I.S. (Iron Man, Marvel) à des fins purement personnelles et techniques.

---

<div align="center">

**Construit avec [Claude Code](https://claude.ai/code)** · Auto-hébergé sur Proxmox · Compatible avec [Argus SOC](https://github.com/Micka420-collab/Argus)

</div>
