#!/usr/bin/env bash
# Jarvis 3.0 — installation one-liner
#   curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Jarvis3.0/main/install.sh | bash
#
# Détecte OS et archi, vérifie Docker, clone, configure les secrets, build, up.
# Idempotent : peut être relancé pour mettre à jour une install existante.

set -euo pipefail

REPO_URL="${JARVIS_REPO_URL:-https://github.com/Micka420-collab/Jarvis3.0.git}"
INSTALL_DIR="${JARVIS_INSTALL_DIR:-$HOME/Jarvis3.0}"
BRANCH="${JARVIS_BRANCH:-main}"

C_BLUE="\033[1;34m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_RESET="\033[0m"

log()   { printf "${C_BLUE}→${C_RESET} %s\n" "$*"; }
ok()    { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn()  { printf "${C_YELLOW}!${C_RESET} %s\n" "$*"; }
fail()  { printf "${C_RED}✗${C_RESET} %s\n" "$*" >&2; exit 1; }

banner() {
  cat <<'EOF'

           ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
           ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
           ██║███████║██████╔╝██║   ██║██║███████╗
      ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
      ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
       ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝

    Assistant domotique auto-hébergé · v0.1.0
    By Micka Delcato
EOF
}

detect_os() {
  case "$(uname -s)" in
    Linux*)   OS=linux ;;
    Darwin*)  OS=macos ;;
    *)        fail "OS non supporté: $(uname -s)" ;;
  esac
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ARCH=amd64 ;;
    arm64|aarch64) ARCH=arm64 ;;
    *) fail "Architecture non supportée: $ARCH" ;;
  esac
  ok "OS : $OS · Archi : $ARCH"
}

check_prereq() {
  log "Vérification des prérequis..."
  for cmd in curl git; do
    command -v "$cmd" >/dev/null 2>&1 || fail "$cmd manquant. Installe-le puis relance."
  done

  if ! command -v docker >/dev/null 2>&1; then
    warn "Docker n'est pas installé."
    if [ "$OS" = "linux" ]; then
      read -r -p "Installer Docker maintenant via le script officiel ? [O/n] " ans
      if [[ ! "$ans" =~ ^[Nn]$ ]]; then
        curl -fsSL https://get.docker.com | sudo sh
        sudo usermod -aG docker "$USER" || true
        ok "Docker installé. Reconnecte-toi pour avoir les permissions, puis relance ce script."
        exit 0
      fi
    else
      fail "Installe Docker Desktop : https://www.docker.com/products/docker-desktop"
    fi
    fail "Installation Docker requise."
  fi
  if ! docker compose version >/dev/null 2>&1; then
    fail "Docker Compose v2 requis. Mets à jour Docker."
  fi
  ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
}

clone_or_update() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Mise à jour du dépôt existant : $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout --quiet "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only --quiet origin "$BRANCH"
    ok "Repo à jour ($(git -C "$INSTALL_DIR" rev-parse --short HEAD))"
  else
    log "Clonage de $REPO_URL → $INSTALL_DIR"
    git clone --branch "$BRANCH" --depth 50 "$REPO_URL" "$INSTALL_DIR"
    ok "Cloné"
  fi
}

random_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "${1:-16}"
  else
    head -c 64 /dev/urandom | xxd -p | tr -d '\n' | head -c $((${1:-16} * 2))
  fi
}

prompt_or_default() {
  local prompt="$1"
  local default="$2"
  read -r -p "$prompt [$default] " ans </dev/tty || true
  printf "%s" "${ans:-$default}"
}

setup_env() {
  cd "$INSTALL_DIR"
  if [ -f .env ]; then
    warn ".env déjà présent — on garde tes secrets."
    return
  fi
  log "Configuration initiale..."
  cp .env.example .env

  # Owner
  local default_user
  default_user="${USER:-mickael}"
  local owner
  owner="$(prompt_or_default "Ton prénom (sera l'owner) ?" "$default_user")"
  sed -i.bak "s/^OWNER_USERNAME=.*/OWNER_USERNAME=${owner}/" .env

  # Domaine
  local domain
  domain="$(prompt_or_default "Domaine LAN (résolu via /etc/hosts ou DNS local) ?" "jarvis.local")"
  sed -i.bak "s/^JARVIS_DOMAIN=.*/JARVIS_DOMAIN=${domain}/" .env

  # Secrets aléatoires
  log "Génération des secrets..."
  local jwt pg_pwd mqtt_pwd
  jwt="$(random_hex 32)"
  pg_pwd="$(random_hex 16)"
  mqtt_pwd="$(random_hex 12)"
  sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=${jwt}|" .env
  sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pg_pwd}|" .env
  sed -i.bak "s|^MQTT_PASSWORD=.*|MQTT_PASSWORD=${mqtt_pwd}|" .env

  # VAPID (Web Push) si node dispo
  if command -v node >/dev/null 2>&1; then
    log "Génération clés VAPID (Web Push)..."
    if local v=$(npx -y -q web-push generate-vapid-keys --json 2>/dev/null); then
      local pub priv
      pub="$(echo "$v" | python3 -c 'import sys,json;print(json.load(sys.stdin)["publicKey"])' 2>/dev/null || echo "")"
      priv="$(echo "$v" | python3 -c 'import sys,json;print(json.load(sys.stdin)["privateKey"])' 2>/dev/null || echo "")"
      if [ -n "$pub" ] && [ -n "$priv" ]; then
        sed -i.bak "s|^VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=${pub}|" .env
        sed -i.bak "s|^VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=${priv}|" .env
        ok "Clés VAPID générées"
      fi
    fi
  else
    warn "node non trouvé : skip VAPID (push notifications désactivées). Installe Node.js puis relance."
  fi

  rm -f .env.bak
  ok "Configuration .env créée"
}

setup_network() {
  if ! docker network inspect proxmox_lan >/dev/null 2>&1; then
    log "Création du réseau Docker partagé proxmox_lan..."
    docker network create proxmox_lan >/dev/null
    ok "Réseau créé"
  else
    ok "Réseau proxmox_lan déjà présent"
  fi
}

download_models() {
  if [ -f "$INSTALL_DIR/models/piper/fr_FR-siwis-medium.onnx" ] || [ -f "$INSTALL_DIR/models/piper/fr_FR-siwis-low.onnx" ]; then
    ok "Modèles Piper déjà présents — skip"
    return
  fi
  log "Téléchargement des modèles (Piper voix fr, ~30 Mo)..."
  bash "$INSTALL_DIR/scripts/download_models.sh" || warn "Téléchargement partiel, vérifie manuellement"
}

build_and_up() {
  cd "$INSTALL_DIR"

  # Vérif espace disque (WSL2 est souvent limité, et containerd plante en I/O error si plein)
  local free_gb
  free_gb="$(df -BG --output=avail /var/lib/docker 2>/dev/null | tail -n1 | tr -dc '0-9' || echo 0)"
  if [ "${free_gb:-0}" -lt 10 ]; then
    warn "Moins de 10 Go libres sur /var/lib/docker — risque de 'input/output error' au build."
    warn "WSL2 ? Étends le VHD ou exécute : docker system prune -a -f"
  fi

  # WSL2 : limite la concurrence BuildKit pour éviter les timeouts containerd
  if grep -qi microsoft /proc/version 2>/dev/null; then
    log "WSL2 détecté — limite BuildKit à 2 jobs concurrents."
    export BUILDKIT_NUM_GOROUTINES=2
    export DOCKER_BUILDKIT=1
  fi

  # Build séquentiel : 11 services en parallèle saturent containerd sur WSL2 / petits hôtes.
  # Plus lent (~+30%) mais robuste — pas de "write /var/lib/containerd/.../meta.db: i/o error".
  local services=(
    gateway llm orchestrator memory iot security vision voice learning agents frontend
  )
  log "Build des images Docker en séquentiel (1ère fois : 8-20 min)..."
  local i=0
  for svc in "${services[@]}"; do
    i=$((i + 1))
    printf "  [%2d/%d] build %s ... " "$i" "${#services[@]}" "$svc"
    if docker compose build --quiet "$svc" 2>/tmp/jarvis-build-err.log; then
      printf "${C_GREEN}✓${C_RESET}\n"
    else
      printf "${C_RED}✗${C_RESET}\n"
      warn "Build de '$svc' échoué — extrait :"
      tail -n 20 /tmp/jarvis-build-err.log >&2 || true
      cat <<EOF

  ${C_YELLOW}Conseils :${C_RESET}
    • WSL2 : ${C_BLUE}wsl --shutdown${C_RESET} puis relance, ou étends le VHD.
    • Espace : ${C_BLUE}docker system prune -a --volumes -f${C_RESET}
    • Reprise : ${C_BLUE}cd $INSTALL_DIR && docker compose build $svc${C_RESET}
EOF
      fail "Build interrompu sur '$svc'."
    fi
  done
  ok "Toutes les images build"

  log "Démarrage des services..."
  docker compose up -d
  ok "Stack lancée"
}

wait_health() {
  log "Attente que le gateway soit healthy..."
  local i
  for i in {1..30}; do
    if docker compose exec -T gateway curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
      ok "Gateway up !"
      return
    fi
    sleep 2
  done
  warn "Gateway tarde à répondre — vérifie : docker compose logs gateway"
}

show_summary() {
  cd "$INSTALL_DIR"
  local domain owner
  domain="$(grep ^JARVIS_DOMAIN= .env | cut -d= -f2)"
  owner="$(grep ^OWNER_USERNAME= .env | cut -d= -f2)"
  cat <<EOF

${C_GREEN}══════════════════════════════════════════════════════════════════════${C_RESET}
${C_GREEN}  Jarvis 3.0 est en route, ${owner}.${C_RESET}
${C_GREEN}══════════════════════════════════════════════════════════════════════${C_RESET}

  Interface web :    https://${domain}
                     (accepte le certificat auto-signé au 1er accès)
  Admin console :    https://${domain}/admin
  Documentation :    ${INSTALL_DIR}/docs/

  ${C_BLUE}Prochaines étapes${C_RESET}
    1. Ajoute "${domain}" dans /etc/hosts pointant vers cet hôte
       echo "127.0.0.1 ${domain}" | sudo tee -a /etc/hosts
    2. Enrôle ta voix-print : cd ${INSTALL_DIR} && make enroll-voice
    3. (optionnel) installe Hermes Agent / OpenClaw pour la délégation
       cd ${INSTALL_DIR} && make build-agents-full
    4. Suis les logs en direct : cd ${INSTALL_DIR} && make logs

  ${C_BLUE}Maintenance${C_RESET}
    cd ${INSTALL_DIR}
    git pull && docker compose up -d --build      # mise à jour
    docker compose logs -f --tail=100             # logs
    make down                                     # arrêt

EOF
}

run_wizard() {
  if [ -t 0 ] && [ -t 1 ] && [ -x "$INSTALL_DIR/scripts/wizard.sh" ]; then
    if [ "${SKIP_WIZARD:-0}" = "1" ]; then
      warn "SKIP_WIZARD=1 — tu pourras le lancer plus tard avec : make wizard"
      return
    fi
    log "Lancement du wizard de connexion (Ctrl+C pour skip)…"
    sleep 1
    bash "$INSTALL_DIR/scripts/wizard.sh" || warn "Wizard interrompu — relance plus tard avec : make wizard"
  else
    warn "Pas de TTY — wizard non lancé. Connecte les features manuellement avec : make wizard"
  fi
}

main() {
  banner
  detect_os
  check_prereq
  clone_or_update
  setup_env
  setup_network
  download_models
  build_and_up
  wait_health
  run_wizard
  show_summary
}

main "$@"
