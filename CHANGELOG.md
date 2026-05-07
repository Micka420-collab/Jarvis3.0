# Changelog

Toutes les modifications notables sont documentées ici.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et ce projet suit le [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Fichiers community GitHub : `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`
- Templates issues (bug, feature, skill share) + template PR
- `FUNDING.yml` pour les sponsors GitHub
- `dependabot.yml` (Python + npm + GitHub Actions + Docker, hebdomadaire)
- Workflows : auto-labeler PRs, stale bot
- `CHANGELOG.md`, `CODEOWNERS`, `AUTHORS.md`

## [0.1.0] - 2026-05-06

Première release publique de Jarvis 3.0.

### Added

#### Core
- Mono-repo Docker Compose : 11 services (gateway, voice, llm, orchestrator, memory, iot, security, vision, learning, agents, federation)
- Gateway FastAPI + Traefik + JWT
- WebSocket bidir `/ws/voice` et `/ws/avatar`
- Frontend React + Three.js (avatar pulsant) + AudioWorklet + PWA installable

#### Voix
- STT faster-whisper (auto-DL au 1er run)
- TTS Piper français (`fr_FR-siwis-medium` par défaut) + ElevenLabs en option
- Wake-word openWakeWord
- Voix-print ECAPA-TDNN + AASIST liveness optionnel
- Streaming TTS phrase-par-phrase + barge-in
- Multi-room audio : `SpeakerRouter` avec mapping caméra→pièce, backends browser/MQTT/Snapcast/HA

#### LLM
- Adapters : Ollama (local), Anthropic Claude, OpenRouter (200+ modèles), Mistral
- Provider Anthropic Vision (multimodal Frigate)
- Streaming SSE
- Tool calling (Anthropic + OpenAI/OpenRouter)
- Memory-augmented prompting (top-K Qdrant injecté en system message)
- Mode agent autonome (chaînage jusqu'à 8 tool calls)

#### Mémoire
- Qdrant + bge-m3 embeddings 1024-d
- Postgres pgvector pour faits structurés
- Skill `remember` + `recall`

#### IoT
- Bridges : Home Assistant REST, Zigbee2MQTT, Z-Wave (zwave-js-ui), MQTT générique, Arduino série
- Discovery automatique avec persistance Postgres
- Gating `requires_admin` configurable

#### Sécurité
- Client WS Argus pour alertes réseau
- Voix-print + challenge phrase + cooldown 30s pour les actions admin
- AASIST anti-deepfake (optionnel)
- DeepfakeDetector (MiniFASNet ONNX + fallback heuristique temporel)
- Rate limiting Traefik (60 req/s + burst 120)
- HSTS + frame-deny + headers sécurité
- fail2ban templates (jail + filter)

#### Vision
- Frigate WS subscriber
- InsightFace recognition
- Branchement automatique `vision.face.recognized` → SpeakerRouter présence

#### Agents externes
- Adapters Hermes (NousResearch), OpenClaw, MCP générique, Mock
- Service `agents` :8005 avec REST + SSE stream
- TaskRegistry persisté en Postgres

#### Console admin web (`/admin`, 10 onglets)
- Dashboard (services + KPIs)
- Connexions (tests live LLM/HA/Argus/Frigate/MQTT)
- Membres (CRUD avec rôles)
- Devices (discovery HA/Z2M, commandes)
- Routines (suggestions apprises + manuelles)
- Builder (drag-and-drop visuel)
- Skills (hot-reload)
- Agents (délégation + tâches récentes)
- Sécurité (Argus + présence + push test)
- Traces (raisonnement)

#### Installation
- `install.sh` : one-liner multi-OS, génère secrets, build, lance
- `install-ubuntu.sh` : auto-installe Docker via apt
- `scripts/wizard.sh` : 11 sections interactives (LLM, HA, Zigbee, Z-Wave, Frigate, Argus, push, multi-room, agents, voix, tests)

#### Déploiement
- Docker Compose avec profiles (gpu, vision, ollama, zigbee, zwave)
- Helm chart Kubernetes (`helm/jarvis/`) avec `values.rpi.yaml` ARM64
- Multi-arch builds (amd64 + arm64)

#### Opérations
- Backup atomique Postgres + Qdrant + Redis + configs (`scripts/backup.sh`)
- Restore avec confirmation (`scripts/restore.sh`)
- Stack monitoring : Prometheus + Grafana + Loki + Promtail + cAdvisor + Node Exporter
- Dashboard Grafana "Jarvis · Overview" pré-provisionné

#### Mobile
- Capacitor config (`@capacitor/core` 6.x, push notifs natives, splash)
- Scripts npm `cap:add:android`, `cap:add:ios`, `cap:copy`, `cap:open:*`

#### Fédération
- Service `federation` :8006 v0.1
- Heartbeat HTTP entre peers (`FEDERATION_PEERS`)
- Endpoints `/health`, `/peers`, `POST /heartbeat`

#### CI / Tests
- GitHub Actions : Python lint+tests, shell, YAML/Helm, smoke build Docker, frontend build
- 24 tests unitaires (autonomous, RAG, OpenRouter, multiroom)
- pytest.ini + conftest.py avec path injection
- Helm lint

#### Documentation
- `README.md` complet avec architecture
- `docs/` : architecture, k3s, raspberry-pi, skills, agents, integrations, operations, federation
- Code de conduite (Contributor Covenant 2.1)
- Politique de sécurité

[Unreleased]: https://github.com/Micka420-collab/Jarvis3.0/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Micka420-collab/Jarvis3.0/releases/tag/v0.1.0
