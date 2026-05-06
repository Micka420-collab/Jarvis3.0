# Phases de livraison Jarvis 3.0

Chaque phase est livrée avec : composants, fichiers principaux, test E2E.

## ✅ Phase 0 — Squelette infra

- `docker-compose.yml` complet (gateway, redis, postgres+pgvector, qdrant, mosquitto, ollama, traefik, frontend nginx ; profile `vision` pour Frigate)
- `.env.example`, `Makefile`, `README.md`, `.gitignore`
- `infra/postgres/init.sql` (schéma : users, voiceprints, auth_events, devices, facts)
- `infra/mosquitto/config/`, `infra/traefik/traefik.yml`, `infra/frigate/config.yml`
- Test : `make up && curl -k https://jarvis.local/api/health`

## ✅ Phase 1 — Voix bidir + LLM hybride + avatar

- `services/voice/`
  - `stt_whisper.py` : faster-whisper int8 / float16
  - `tts_piper.py` + `tts_eleven.py` : provider swappable
  - `vad.py` : silero VAD avec `StreamSegmenter` (segmentation auto utterances)
  - `wakeword.py` : openWakeWord
  - `visemes.py` : amplitude RMS → ouverture mâchoire (fallback sans phonèmes)
- `services/llm/` : router + adapters Ollama / Anthropic Claude / Mistral
- `services/orchestrator/` : boucle transcript → LLM → tool calling → TTS
- `services/gateway/app/ws/voice.py` : WS bidirectionnel
- `frontend/`
  - Avatar 3D Three.js : icosaèdre + mâchoire animée par visèmes
  - AudioWorklet capture mic + lecteur PCM streaming
  - Hook `useVoiceWS` qui pousse `viseme` au composant Avatar
- Tests : `tests/e2e/test_phase1_voice.py`
- **Test E2E** : navigateur → bouton "● parler" → "bonjour" → réponse vocale + mâchoire bouge

## ✅ Phase 2 — Mémoire + voix-print

- `services/memory/` : Qdrant + bge-m3 + REST `/remember` `/recall`
- `services/voice/app/voiceprint.py` : ECAPA-TDNN, intégration Postgres pgvector
- `services/voice/app/main.py:OwnerStore` : charge l'embedding owner et calcule la similarité live → publie `voice.identity.verified` correct
- `scripts/enroll_voiceprint.py` : 5 phrases, embedding moyen
- `services/orchestrator/app/identity.py` : `IdentityStore` qui consomme les events
- `services/orchestrator/app/challenge.py` : challenge phrase dynamique 3 mots, TTL 30s
- Gating dans `orchestrator/app/main.py` : tools admin → vérif owner+similarité, sinon challenge
- Tests : `tests/unit/test_challenge.py`, `tests/unit/test_identity.py`
- **Test E2E** : `make enroll-voice` → "souviens-toi que mon film préféré est Inception" → reboot → "quel est mon film préféré". Voix tierce → commande admin refusée + challenge.

## ✅ Phase 3 — Argus

- `services/security/app/argus_ws.py` : client WS JWT avec reconnexion exponentielle
- `services/security/app/alert_mapper.py` : alerte → phrase TTS, **enrichi MITRE ATT&CK** (TA000x + T1xxx traduits FR)
- `services/security/app/main.py` : endpoints `/silence`, `/test/alert`
- `services/gateway/app/routes/security.py:silence` : double gating JWT owner + voix-print via `voice_session_id`
- `services/orchestrator/app/main.py:identity` : endpoint exposant l'état d'authentification voix
- Tests : `tests/unit/test_alert_mapper.py`, `tests/unit/test_alert_mapper_mitre.py`
- **Test E2E** : `curl -X POST http://localhost:8003/test/alert -d '{"severity":"critical","host":"192.168.1.42","rule":"port scan","raw":{"mitre":{"tactic":["TA0007"],"technique":["T1046"]}}}'` → Jarvis annonce "alerte critique sur 192.168.1.42 — port scan (découverte du réseau, scan de ports)"

## ✅ Phase 4 — IoT

- `services/iot/` : 3 transports unifiés (`devices.yaml` registre)
- `mqtt_bridge.py` : publish + **subscribe states** (push sur le bus)
- `ha_bridge.py` : commandes + `list_entities()` pour la **HA discovery**
- `serial_bridge.py` : protocole JSON-line + callback states publié sur le bus
- `main.py` : endpoint `/discover/ha` qui upsert les entités HA dans la table `devices`
- `examples/arduino/garage_door.ino` : firmware exemple Arduino (relais + capteur reed)
- Tools LLM `iot_command` / `iot_state`
- **Test E2E** : "allume le salon" (HA), "ferme les volets" (MQTT ESP32), "ouvre le garage" (série, owner-only). `make discover-ha` peuple la BDD depuis HA.

## ✅ Phase 5 — Vision

- `services/vision/`
  - `frigate_consumer.py` : WS Frigate + fetch `/api/<cam>/latest.jpg`
  - `face_recog.py` : InsightFace buffalo_l, recharge `/models/known_faces`
  - `main.py` : event `vision.face.recognized` + TTS proactif "Bonjour <nom>"
- `infra/frigate/config.yml` : exemple 2 caméras RTSP
- `scripts/enroll_face.py` : enrôle depuis image OU webcam, valide via InsightFace
- Service docker `frigate` ajouté en profile `vision` → `make up-vision`
- **Test E2E** : `make enroll-face name=mickael image=./photo.jpg` puis passer devant la caméra → "Bonjour mickael"

## Tests

- **Unit** (`tests/unit/`) : alert_mapper (sévérité + MITRE), challenge phrase, identity store, schémas events
- **E2E** (`tests/e2e/`) : health phase 0, voice text bypass phase 1
- À compléter : E2E phase 4 (mock HA + simulation MQTT), phase 5 (mock Frigate)
