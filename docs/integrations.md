# Guide d'intégration des sections

Ce document détaille **chaque service que Jarvis peut connecter**, dans l'ordre du wizard interactif (`make wizard`). Pour chaque section :

- 🛠 prérequis (matériel, comptes, ports)
- 🔑 où récupérer les credentials
- 📝 vars `.env` correspondantes
- ✅ comment tester la connexion (CLI + admin)
- 🧯 erreurs fréquentes

> **Rappel** : tout est skippable. Tu peux n'activer que ce dont tu as besoin et revenir plus tard via `make wizard` ou l'onglet `/admin → Connexions`.

---

## 1. LLM — le cerveau de Jarvis

Trois providers supportés. Choisis-en un.

### 1.a · Anthropic Claude (cloud, recommandé)

| | |
|---|---|
| 🛠 prérequis | compte [console.anthropic.com](https://console.anthropic.com) avec crédit |
| 🔑 credentials | API Key dans Settings → API Keys |
| 📝 vars | `LLM_PROVIDER=anthropic` · `ANTHROPIC_API_KEY=sk-ant-...` · `LLM_MODEL=claude-sonnet-4-6` |
| ✅ test admin | `/admin → Connexions → 1. Anthropic` → bouton **Tester** |
| ✅ test CLI | `curl https://api.anthropic.com/v1/messages -H "x-api-key:$KEY" -H "anthropic-version: 2023-06-01" -d '{"model":"claude-sonnet-4-6","max_tokens":8,"messages":[{"role":"user","content":"ping"}]}'` |

Modèles recommandés :
- **Opus 4.7** (`claude-opus-4-7`) : raisonnement complexe, agent autonome
- **Sonnet 4.6** (`claude-sonnet-4-6`) : équilibre qualité/latence (par défaut)
- **Haiku 4.5** (`claude-haiku-4-5-20251001`) : ultra-rapide, briefing matinal
- **Vision** : `LLM_PROVIDER=anthropic-vision` ajoute la frame caméra Frigate au prompt

### 1.b · Ollama (local, sans cloud)

| | |
|---|---|
| 🛠 prérequis | 8 Go RAM mini (16 Go recommandé) · GPU NVIDIA optionnel pour les gros modèles |
| 🔑 credentials | aucune |
| 📝 vars | `LLM_PROVIDER=ollama` · `LLM_MODEL=llama3.1:8b` · `OLLAMA_HOST=http://ollama:11434` |
| ✅ pull modèle | `docker compose --profile ollama up -d ollama && docker compose exec ollama ollama pull llama3.1:8b` |
| ✅ test | `/admin → Connexions → 1bis. Ollama` |

Modèles testés sur Pi 5 8 Go : `llama3.2:1b` (5 tok/s), `llama3.2:3b` (1.5 tok/s).

### 1.c · Mistral (cloud Europe)

| | |
|---|---|
| 🔑 credentials | [console.mistral.ai](https://console.mistral.ai) → API Keys |
| 📝 vars | `LLM_PROVIDER=mistral` · `MISTRAL_API_KEY=...` · `LLM_MODEL=mistral-large-latest` |

### 🧯 Erreurs LLM
- `401 invalid x-api-key` → vérifie l'absence d'espaces / vérifier que la clé est active
- `model not found` → liste les modèles dispo : `curl https://api.anthropic.com/v1/models -H "x-api-key:$KEY"`
- Ollama : `connection refused` → le service `ollama` n'est pas dans le profil démarré (`--profile ollama`)

---

## 2. Home Assistant

Plug-and-play : Jarvis pilote tes lumières, prises, switches HA via l'API REST + WebSocket.

| | |
|---|---|
| 🛠 prérequis | HA accessible via HTTP (LAN ou Cloudflare Tunnel) |
| 🔑 credentials | HA → ton profil utilisateur → bas de page → **Long-Lived Access Tokens → Create Token** |
| 📝 vars | `HA_BASE_URL=http://homeassistant.local:8123` · `HA_LONG_LIVED_TOKEN=eyJ0eXA...` |
| ✅ test admin | `/admin → Connexions → 2. Home Assistant` |
| ✅ test CLI | `curl -H "Authorization: Bearer $TOK" $URL/api/` → `{"message":"API running."}` |
| ✅ découverte | `/admin → Devices → "Découvrir Home Assistant"` (importe toutes les entités `light.*`, `switch.*`, `media_player.*`) |

### 🧯 Erreurs HA
- `401` : token révoqué ou copié incomplet (vérifie le préfixe `eyJ0`)
- `Network unreachable` : ajoute le réseau HA à `proxmox_lan` dans compose
- entités absentes : Jarvis ne récupère que `light/switch/media_player` — étend `services/iot/app/ha_bridge.py` pour d'autres domains

---

## 3. Zigbee via Zigbee2MQTT

Pour piloter un dongle Zigbee (Sonoff, Conbee II, SkyConnect…) sans passer par HA.

| | |
|---|---|
| 🛠 prérequis | dongle USB Zigbee branché à l'hôte |
| 🔑 credentials | aucune (MQTT broker interne) |
| 📝 vars | `ZIGBEE_ADAPTER=/dev/ttyACM0` · profile `zigbee` activé |
| ✅ démarrer | `docker compose --profile zigbee up -d zigbee2mqtt` |
| ✅ UI Z2M | `https://z2m.${JARVIS_DOMAIN}` (frontend Z2M) |
| ✅ découverte | `/admin → Devices → "Découvrir Zigbee2MQTT"` |

Pour autoriser l'appairage : Z2M UI → **Permit join** 4 min, presse le bouton de chaque appareil.

### 🧯 Erreurs Zigbee
- `permission denied /dev/ttyACM0` → `sudo usermod -aG dialout $USER` puis re-login
- `port already used` → un autre conteneur (Z-Wave, ConBee) tient le port
- ampoule qui ne répond pas : reset de l'appareil (cf. doc constructeur), then "Permit join"

---

## 4. Z-Wave via zwave-js-ui

| | |
|---|---|
| 🛠 prérequis | dongle Z-Wave (Aeotec Z-Stick, Zooz 800LR…) |
| 🔑 credentials | aucune sauf si tu actives l'auth dans zwave-js-ui (recommandé) |
| 📝 vars | `ZWAVE_ADAPTER=/dev/ttyUSB-zwave` · `ZWAVE_API_URL=http://zwave-js-ui:8091` · `ZWAVE_API_TOKEN=...` |
| ✅ démarrer | `docker compose --profile zwave up -d zwave-js-ui` |
| ✅ UI | `https://zwave.${JARVIS_DOMAIN}` |
| ✅ inclusion | UI → **Smart Start** ou Inclusion classique → suit le manuel de l'appareil |
| ✅ découverte | `POST /api/admin/devices/discover/zwave` (depuis admin) |

Le bridge Jarvis lit les nœuds via `GET /api/v1/nodes` et les commandes vont sur le topic MQTT `zwave/<nodeID>/set`.

### 🧯 Erreurs Z-Wave
- adapter non détecté : `ls -l /dev/serial/by-id/` puis crée un lien symbolique `/dev/ttyUSB-zwave`
- inclusion qui timeout : assure-toi que le dongle est <2 m de l'appareil pendant l'inclusion

---

## 5. Frigate (caméras + Claude Vision)

Permet à Jarvis de répondre à *« qu'est-ce que tu vois sur la caméra du salon ? »* en envoyant la dernière frame à Claude Vision.

| | |
|---|---|
| 🛠 prérequis | Frigate déjà déployé (LAN ou Docker compose séparé) |
| 🔑 credentials | aucune si LAN, sinon authentification Frigate (voir leur doc) |
| 📝 vars | `FRIGATE_API_URL=http://frigate:5000` · `LLM_PROVIDER=anthropic-vision` |
| ✅ test admin | `/admin → Connexions → 4. Frigate` |
| ✅ test CLI | `curl $FRIGATE_API_URL/api/version` |

Pour utiliser Vision dans une question, ajoute `vision_camera=<nom>` dans le prompt (ou laisse Jarvis détecter automatiquement la pièce d'occupation et choisir la caméra). La frame JPEG est encodée en base64 et envoyée comme `image_block` Anthropic.

### 🧯 Erreurs Vision
- `latest.jpg` 404 : le nom de caméra ne correspond pas à `frigate/cameras/<name>`
- réponse vague : Sonnet 4.6 nécessite parfois "Décris précisément ce que tu vois en énumérant les objets"

---

## 6. Argus (alertes réseau / IPS)

[Argus](https://github.com/Micka420-collab/Argus) est l'IPS maison qui surveille les anomalies LAN. Jarvis remonte ses alertes dans la pop-up admin et peut les énoncer vocalement.

| | |
|---|---|
| 🛠 prérequis | Argus déployé sur le même `proxmox_lan` |
| 🔑 credentials | `argus user create-token` |
| 📝 vars | `ARGUS_BASE_URL=http://argus:9000` · `ARGUS_API_TOKEN=...` |
| ✅ test admin | `/admin → Connexions → 3. Argus` |
| ✅ flow | Argus webhook POST `/api/security/alert` → notif push + voix si owner présent |

### 🧯 Erreurs Argus
- `connection refused` : ajoute le service Argus au réseau Docker partagé `proxmox_lan`

---

## 7. Push notifications (Web Push)

PWA installable. Notifications natives sur le verrouillage (Android, iOS 16+, desktop).

| | |
|---|---|
| 🛠 prérequis | HTTPS valide (Let's Encrypt ou cert de confiance) — iOS exige TLS valide pour les push |
| 🔑 credentials | clés VAPID auto-générées par `install.sh` |
| 📝 vars | `VAPID_PUBLIC_KEY=BJD...` · `VAPID_PRIVATE_KEY=...` · `VAPID_CONTACT_EMAIL=mailto:moi@exemple.fr` |
| ✅ activation | ouvre l'app sur ton téléphone → bouton **Activer les notifications** dans le header |
| ✅ test admin | `/admin → Sécurité → "Envoyer un push de test"` |

### 🧯 Erreurs Push
- iOS ne reçoit rien : la PWA doit être **ajoutée à l'écran d'accueil** d'abord
- `410 Gone` : la subscription est expirée → re-s'abonner depuis l'app
- desktop muet : autorise les notifs dans le navigateur (icône cadenas → Notifications → autoriser)

---

## 8. Multi-room audio

Le TTS Jarvis est routé vers l'enceinte de la pièce occupée. Si toutes les enceintes de cette pièce sont busy, fallback vers une autre libre.

| | |
|---|---|
| 🛠 prérequis | une enceinte par pièce, accessible en : Snapcast, MQTT (ESP32 dédié), HA `media_player`, ou simplement le navigateur |
| 📝 fichier | `services/voice/app/speakers.yaml` |
| ✅ après édition | `docker compose restart voice` |

Exemple :

```yaml
speakers:
  - id: browser_main
    name: Navigateur Jarvis (UI)
    room: any
    kind: browser
    default: true

  - id: salon_kef
    name: KEF Salon
    room: salon
    kind: snapcast
    url: http://snapcast:1780/streams/salon

  - id: chambre_googlehome
    name: Google Home Chambre
    room: chambre
    kind: homeassistant
    entity_id: media_player.chambre

  - id: cuisine_esp32
    name: Speaker ESP32 Cuisine
    room: cuisine
    kind: mqtt
    topic: jarvis/speakers/cuisine/play
```

Le routeur a 4 backends :

| `kind` | Description | Notes |
|---|---|---|
| `browser` | WebSocket vers l'UI Jarvis (par défaut) | utilisé si aucune autre enceinte ne match |
| `mqtt` | Publie `{pcm_b64, viseme}` sur le topic | ton client ESP32 décode et joue |
| `snapcast` | POST PCM brut sur l'URL stream | requiert un serveur Snapcast |
| `homeassistant` | `media_player.play_media` avec `data:audio/wav;base64,...` | nécessite `HA_BASE_URL` et `HA_LONG_LIVED_TOKEN` |

La **pièce occupée** est déduite des events `vision.face.recognized` (caméras Frigate) et `presence.zone.entered` (capteurs présence). Le router maintient un timestamp par pièce.

---

## 9. Agents externes (Hermes / OpenClaw / MCP)

Jarvis peut **déléguer** des tâches PC réelles : navigation web, fichiers, OS, services en ligne.

| | |
|---|---|
| 🛠 prérequis | binaires `hermes` et/ou `openclaw` accessibles depuis le service `agents` |
| 📝 vars | `INSTALL_HERMES=true` · `INSTALL_OPENCLAW=true` · ou bind-mount des binaires host |
| ✅ build image | `make build-agents-full` (~1 Go) |
| ✅ test admin | `/admin → Agents → "Déléguer une tâche"` |
| 📚 doc complète | [`docs/agents.md`](agents.md) |

Tools LLM exposés :
- `agent_list` — liste des agents disponibles
- `agent_delegate(agent, goal)` — délègue (gated `requires_admin`)
- `agent_task_status(task_id)`
- `agent_task_cancel(task_id)`

---

## 10. Voix-print + visage (sécurité multi-utilisateur)

Permet à Jarvis de reconnaître **qui parle** et **qui se présente devant la caméra**. Indispensable pour gater les actions admin.

### Voix

| | |
|---|---|
| 🛠 prérequis | micro + voix-print model SpeechBrain (auto-DL au 1er run) |
| ✅ enrôlement | `make enroll-voice` (CLI) ou `/admin → Membres → … → Enrôler la voix` |
| ✅ rapide | enregistre 3 phrases de ~5 s chacune |
| 📝 thresholds | `VOICEPRINT_THRESHOLD_ACCEPT=0.75` · `VOICEPRINT_THRESHOLD_GREY=0.65` |

Si score ≥ 0.75 → accepté. Entre 0.65 et 0.75 → challenge phrase. < 0.65 → rejeté + alerte.

### Visage

| | |
|---|---|
| 🛠 prérequis | webcam ou caméra IP → service `vision` actif |
| ✅ enrôlement | `/admin → Membres → … → Enrôler le visage` (capture via webcam UI) |
| 📝 vars | `FACE_RECOGNITION_THRESHOLD=0.5` |

L'AASIST liveness check empêche les attaques par photo / vidéo replay.

---

## 11. Routines apprises

Jarvis observe tes habitudes et propose des automatisations. Tu valides ce que tu veux activer.

| | |
|---|---|
| 📝 vars | `LEARN_PATTERN_MIN_SAMPLES=5` (5 occurrences mini avant suggestion) · `LEARN_PATTERN_MIN_DAYS=3` |
| ✅ admin | `/admin → Routines → "Suggestions apprises"` |

Exemple : tu allumes le salon à ~19h chaque soir → après 5 jours, Jarvis propose la routine "tous les jours, 19h00, light.salon ON" → tu actives.

---

## 12. Bonus — OAuth Google (Gmail / Calendar)

Pour les délégations OpenClaw/Hermes qui touchent Gmail ou Google Calendar.

| | |
|---|---|
| 🛠 prérequis | projet Google Cloud avec OAuth Client (Desktop) |
| 🔑 credentials | `client_secret_xxxx.json` à mettre dans `~/.config/openclaw/` |
| ✅ flow | au 1er appel, OpenClaw ouvre ton navigateur → Google consent screen |

> **Sécurité** : ces tokens donnent un accès puissant. Limite les scopes (`gmail.readonly` plutôt que `gmail.modify`) et révoque depuis [myaccount.google.com](https://myaccount.google.com/permissions) au moindre doute.

---

## Ordre recommandé d'intégration

Pour une mise en route fluide, intègre dans cet ordre :

1. **LLM** (sinon Jarvis ne pense pas) → indispensable
2. **Voix-print owner** → débloque les tools admin
3. **Home Assistant** OU **Zigbee/Z-Wave** → premier contrôle réel
4. **Push notifs** → alertes immédiates
5. **Argus** → si tu l'as déjà
6. **Frigate + Vision** → quand tu veux le multimodal
7. **Multi-room** → quand tu as ≥ 2 enceintes
8. **Agents externes** → pour les tâches complexes auto

Aucune section n'est bloquante : Jarvis fonctionne avec juste un LLM et une voix.

---

## Astuce : tout vérifier d'un coup

```bash
# CLI
make wizard          # relance interactif
make logs            # streame les logs
bash scripts/healthcheck.sh    # health-check rapide

# Web
https://jarvis.local/admin  → Connexions   # tests live de chaque service
                            → Dashboard    # KPIs + état services
```

Pour tout ré-initialiser depuis zéro (⚠ supprime la base) :

```bash
docker compose down -v
rm .env
bash install.sh
```
