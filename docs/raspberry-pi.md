# Jarvis sur Raspberry Pi (ARM64)

Déploiement sur Raspberry Pi 4 ou 5 avec Raspberry Pi OS 64-bit (bookworm) ou Ubuntu Server 24.04 ARM64.

## Matériel recommandé

| Composant | Pi 4 (4 Go) | Pi 5 (8 Go) recommandé |
|---|---|---|
| Stockage | SSD USB3 (microSD = lent) | NVMe via HAT M.2 |
| Refroidissement | Boîtier ventilé | Active cooler officiel |
| Audio | DAC USB ou ReSpeaker | Idem |
| Vision | Ø (Frigate trop lourd) | Coral USB Edge TPU + caméra IP |
| Zigbee | SkyConnect, ConBee II ou Sonoff Zigbee 3.0 USB | Idem |

## Choix d'architecture

Sur Pi 4, le LLM local n'est pas viable (Llama 8B → 30 tok/s en GPU desktop, ~0,5 tok/s en CPU Pi). Deux options :

| Profil | LLM | Avantages |
|---|---|---|
| **Local-only (recommandé)** | Désactivé, Claude / Mistral via API | Pas de latence locale, qualité optimale |
| **Léger local** | Llama 3.2 1B (Q4) via Ollama | 100 % offline, latence ~3 s |

Le fichier `docker-compose.rpi.yml` configure le profil `local-only` par défaut (Anthropic Claude Haiku, le plus rapide). Pour activer Ollama local : `docker compose --profile llm-local -f docker-compose.yml -f docker-compose.rpi.yml up -d`.

## Installation

### 1. Préparer l'OS

```bash
# Sur le Pi (Raspberry Pi OS 64-bit ou Ubuntu Server 24.04)
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y docker.io docker-compose-plugin git make
sudo usermod -aG docker $USER && newgrp docker

# Optionnel : SSD via USB3
# Suivre https://www.raspberrypi.com/documentation/computers/configuration.html#boot-from-usb-mass-storage
```

### 2. Cloner & configurer

```bash
git clone https://github.com/Micka420-collab/Jarvis3.0.git
cd Jarvis3.0
cp .env.example .env
$EDITOR .env
# Régler au minimum :
#   JWT_SECRET, POSTGRES_PASSWORD, OWNER_USERNAME
#   LLM_PROVIDER=anthropic
#   ANTHROPIC_API_KEY=sk-ant-...
#   TTS_PROVIDER=piper (ou elevenlabs si tu préfères la qualité)
#   PIPER_VOICE=fr_FR-siwis-low
```

### 3. Démarrer

```bash
make download-models      # Piper voix fr (~30 Mo en low / ~50 Mo en medium)
make up-rpi               # avec les overrides ARM64
make logs s=voice         # vérifier que Whisper tiny charge bien
```

> **Note 1er boot** : la première exécution de `make up-rpi` build localement les images Docker (faster-whisper / CTranslate2 / torch / sentence-transformers) — comptez **15 à 25 minutes** sur Pi 5 SSD, **30 à 45 minutes** sur Pi 4 microSD. Les builds suivants sont incrémentaux (~30 s).
>
> Pour éviter le build local, push d'abord les images via `make build-multiarch` depuis un poste x86 (utilise buildx) puis `docker compose pull` sur le Pi.

### 4. Tester

```bash
curl -k https://jarvis.local/api/health
open https://jarvis.local
```

Sur la PWA (`https://jarvis.local`), Android propose "Ajouter à l'écran d'accueil" → tu obtiens une app installée.

## Performances mesurées (Pi 5 8 Go, SSD NVMe)

| Métrique | Mesure |
|---|---|
| Boot complet de la stack | ~30 s |
| Whisper tiny FR 5 s d'audio | ~400 ms |
| Piper fr_FR-siwis-low 1 phrase | ~150 ms |
| Round-trip voix complet (cloud Claude Haiku) | ~1,8 s |
| RAM idle / sous charge | 1,2 Go / 2,8 Go |

Sur Pi 4 (4 Go), prévoir +800 ms sur Whisper et désactiver la mémoire vectorielle (Qdrant) en faveur de pgvector seul si la RAM manque.

## Périphériques USB

Pour brancher Arduino + Zigbee adapter en même temps, créer des aliases udev stables :

```bash
sudo nano /etc/udev/rules.d/99-jarvis.rules
# Y ajouter (adapter VID/PID à tes périphériques) :
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="ttyUSB-arduino"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="ttyUSB-zigbee"

sudo udevadm control --reload-rules && sudo udevadm trigger
```

Puis dans `.env` :
```
ARDUINO_SERIAL_PORTS=/dev/ttyUSB-arduino
```
Et dans `infra/zigbee2mqtt/configuration.yaml` :
```yaml
serial:
  port: /dev/ttyUSB-zigbee
```

## Pi 4 (4 Go) : ajustement mémoire

Les `mem_limit` du fichier `docker-compose.rpi.yml` totalisent ~5,9 Go : confortable sur Pi 5 (8 Go), trop juste sur Pi 4 (4 Go). Pour Pi 4, copier le snippet suivant dans `docker-compose.override.yml` pour serrer encore :

```yaml
services:
  voice:    { deploy: { resources: { limits: { memory: 1200m } } } }
  llm:      { deploy: { resources: { limits: { memory: 400m } } } }
  memory:   { deploy: { resources: { limits: { memory: 700m } } } }
  orchestrator: { deploy: { resources: { limits: { memory: 300m } } } }
  postgres: { deploy: { resources: { limits: { memory: 400m } } } }
  qdrant:   { deploy: { resources: { limits: { memory: 400m } } } }
  gateway:  { deploy: { resources: { limits: { memory: 300m } } } }
```

Activer aussi zswap :
```bash
sudo sed -i 's/^#zswap.enabled.*/zswap.enabled=1/' /boot/firmware/cmdline.txt
sudo reboot
```

## Limites connues

- **Frigate désactivé par défaut** : le Pi 4 ne tient pas le détecteur sans Coral USB. Sur Pi 5 + Coral, activer avec `make up-rpi-vision` (raccourci équivalent à `--profile vision-rpi`).
- **AASIST liveness** : fonctionne avec onnxruntime CPU, ajouter ~150 ms par utterance.
- **Avatar GLTF** : prévoir un GLTF léger (textures 512×512) pour fluidité 60 fps.

## Mise à jour

```bash
git pull
make build           # ou : docker compose -f docker-compose.yml -f docker-compose.rpi.yml build
make up-rpi
```

Pour mises à jour automatiques, ajouter un cron :
```cron
0 4 * * * cd /home/pi/Jarvis3.0 && git pull && make up-rpi >> /var/log/jarvis-update.log 2>&1
```
