# Phases de livraison Jarvis 3.0

Chaque phase est livrée avec : composants, fichiers principaux, test E2E.

## ✅ Phase 0 — Squelette infra

- `docker-compose.yml` complet (gateway, redis, postgres+pgvector, qdrant, mosquitto, ollama, traefik, frontend nginx)
- `.env.example`, `Makefile`, `README.md`, `.gitignore`
- `infra/postgres/init.sql` (schéma : users, voiceprints, auth_events, devices, facts)
- `infra/mosquitto/config/`, `infra/traefik/traefik.yml`
- Test : `make up && curl -k https://jarvis.local/api/health`

## 🚧 Phase 1 — Voix bidir + LLM hybride + avatar

- `services/voice/` (faster-whisper STT, Piper/ElevenLabs TTS, openWakeWord, ECAPA voice-print stub)
- `services/llm/` (router LiteLLM, adapters Ollama/Anthropic/Mistral)
- `services/orchestrator/` (boucle transcript → LLM → TTS, tool registry)
- `services/gateway/app/ws/voice.py` (WebSocket bidirectionnel)
- `frontend/` (React + Vite + Three.js avatar pulsant)
- Test : navigateur → bouton "● parler" → "bonjour" → réponse vocale + avatar pulse, latence cible <2s

**À compléter pour finaliser la phase :**
- VAD silero (segmentation utterances)
- streaming partial transcripts
- avatar GLTF + visèmes Oculus 15

## 🚧 Phase 2 — Mémoire + voix-print

- `services/memory/` (Qdrant + bge-m3 embedder + REST `/remember` `/recall`)
- `services/voice/app/voiceprint.py` (ECAPA, intégration Postgres pgvector)
- `scripts/enroll_voiceprint.py`
- `services/orchestrator/app/tools/registry.py` : tools `memory_remember` / `memory_recall`
- Test : `make enroll-voice` → "souviens-toi que mon film préféré est Inception" → reboot → "quel est mon film préféré"

**À compléter :**
- comparer embedding live à l'owner stocké et publier `voice.identity.verified`
- décorateur `require_owner_voice` câblé sur les routes IoT/sécurité
- challenge phrase dynamique côté orchestrator

## 🚧 Phase 3 — Argus

- `services/security/app/argus_ws.py` (client WS JWT)
- `services/security/app/alert_mapper.py` (alerte → phrase TTS)
- `services/security/app/main.py` (endpoint `/silence`, `/test/alert`)
- Test : `curl -X POST http://localhost:8003/test/alert -d '{"severity":"critical","host":"192.168.1.42","rule":"port scan"}'` → Jarvis annonce vocalement

**À compléter :**
- déployer Argus à côté
- mapper les règles MITRE ATT&CK importantes
- routes admin `/silence` gated voix-print

## 🚧 Phase 4 — IoT

- `services/iot/` (MQTT + HA + série), registre `devices.yaml`
- Tools LLM `iot_command` / `iot_state`
- Test : "allume le salon" (HA), "ferme les volets" (MQTT), "ouvre le garage" (série, owner-only)

**À compléter :**
- firmware Arduino exemple (`docs/arduino-firmware-example.ino`)
- découverte automatique HA entities
- état temps réel poussé au bus

## 🚧 Phase 5 — Vision

- `services/vision/` (Frigate consumer + InsightFace)
- Test : passage devant caméra → "Bonjour Mickaël"

**À compléter :**
- script `scripts/enroll_face.py`
- intégration Frigate config exemple

## Tests E2E

`tests/e2e/` (à compléter) avec :
- httpx + pytest-asyncio
- fixtures audio pré-enregistrées (FR, owner et tiers)
- mock Argus WS
