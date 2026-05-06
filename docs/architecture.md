# Architecture Jarvis 3.0

## Vue d'ensemble

```
CLIENT (React + Three.js avatar GLTF + WebRTC mic)
     │ HTTPS / WSS (JWT)
GATEWAY FastAPI (auth, WS voice/avatar, reverse proxy Traefik)
     │
     ├── voice  : faster-whisper (STT) + Piper/ElevenLabs (TTS) + openWakeWord + ECAPA voix-print
     ├── llm    : LiteLLM router → Ollama | Anthropic Claude | Mistral
     ├── memory : Qdrant (vecteurs) + Postgres (faits, users, audit)
     ├── orchestrator : intents + tool calling (iot, security, memory, time)
     ├── iot    : Mosquitto MQTT + bridge Home Assistant + bridge série pyserial
     ├── vision : Frigate (NVR/RTSP) + InsightFace (reco faciale)
     └── security : client WS Argus + mapper alerte→phrase TTS
            │
       Bus interne Redis Streams (events, replay)
            │
INFRA Docker : Mosquitto, Qdrant, Postgres, MinIO, Frigate
EXTERNES     : Home Assistant, Argus, Ollama, Arduino USB
```

## Bus d'événements

Tous les services se parlent via **Redis Streams** (durables, replay-able). Les schémas sont définis dans `services/_shared/events.py` (Pydantic).

| Stream | Producteur | Consommateur principal |
|---|---|---|
| `voice.audio.chunk` | gateway (WS) | voice (STT) |
| `voice.transcript.ready` | voice | orchestrator |
| `voice.identity.verified` | voice | gateway, orchestrator |
| `intent.response.ready` | orchestrator, security, vision | voice (TTS) |
| `tts.audio.chunk` | voice | gateway (WS → UI) |
| `iot.device.commanded` | iot | bus (audit) |
| `argus.alert.received` | security | orchestrator, UI |
| `memory.fact.stored` | memory | UI |
| `vision.face.recognized` | vision | orchestrator, UI |

Pub/sub volatile (pas de replay) sur `ui.argus`, `ui.iot`, `ui.vision`, `ui.state` pour pousser à l'UI.

## Réseau Docker

Deux réseaux :
- `jarvis-net` (interne) — tous les services Jarvis
- `proxmox_lan` (externe) — partagé avec Argus et Home Assistant

Seul Traefik bind sur l'hôte (80/443). Le dashboard Traefik est exposé sur 8080 (à protéger derrière le LAN).

## TLS LAN

Traefik gère les certificats auto-signés pour `jarvis.local`. Pour ajouter un cert Let's Encrypt en LAN, ajouter un resolver DNS challenge.

## Provider-agnostic LLM/TTS

`services/llm/app/router.py` choisit dynamiquement l'adapter via `LLM_PROVIDER` (`ollama` / `anthropic` / `mistral`).
`services/voice/app/main.py:make_tts()` choisit `piper` (local) ou `elevenlabs` (cloud).
On peut basculer par redémarrage de service sans toucher au code applicatif.
