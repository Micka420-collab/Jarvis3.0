#!/usr/bin/env bash
# Jarvis 3.0 — installation Ubuntu en une commande
#
#   curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Jarvis3.0/main/install-ubuntu.sh | bash
#
# Différences avec install.sh :
# - Vérifie que c'est bien Ubuntu/Debian (apt)
# - Installe automatiquement Docker Engine + Compose v2 via apt
# - Installe les dépendances système (curl, git, openssl, python3, nodejs)
# - Configure le pare-feu UFW (ports 80/443) si présent
# - Ajoute l'utilisateur au groupe docker
# - Puis enchaîne sur install.sh

set -euo pipefail

C_BLUE="\033[1;34m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_RESET="\033[0m"

log()   { printf "${C_BLUE}→${C_RESET} %s\n" "$*"; }
ok()    { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn()  { printf "${C_YELLOW}!${C_RESET} %s\n" "$*"; }
fail()  { printf "${C_RED}✗${C_RESET} %s\n" "$*" >&2; exit 1; }

REPO_URL="${JARVIS_REPO_URL:-https://github.com/Micka420-collab/Jarvis3.0.git}"
INSTALL_DIR="${JARVIS_INSTALL_DIR:-$HOME/Jarvis3.0}"
BRANCH="${JARVIS_BRANCH:-main}"

banner() {
  cat <<'EOF'

      ████████╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ╚█╔══█╔╝██╔══██╗██╔══██╗██║   ██║██║██╔════╝
        ╚═╝█╔╝ ███████║██████╔╝██║   ██║██║███████╗
        ╚╝█╔╝  ██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
         █╔╝   ██║  ██║██║  ██║ ╚████╔╝ ██║███████║
         ╚╝    ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝

    Installation Ubuntu/Debian · v0.1.0
EOF
}

require_ubuntu() {
  if [ ! -f /etc/os-release ]; then
    fail "Ce script est pour Ubuntu/Debian. Utilise install.sh sinon."
  fi
  . /etc/os-release
  case "${ID:-}" in
    ubuntu|debian|raspbian|linuxmint|pop) ok "Distribution détectée : $PRETTY_NAME" ;;
    *)
      warn "Distribution inattendue ($ID) — on tente quand même."
      ;;
  esac
}

require_sudo() {
  if [ "$EUID" -eq 0 ]; then
    SUDO=""
    ok "Exécution en root"
  else
    if command -v sudo >/dev/null 2>&1; then
      SUDO="sudo"
      log "Tu vas être prompté pour sudo."
      $SUDO -v || fail "sudo refusé"
      # keepalive sudo en arrière-plan
      ( while true; do sudo -nv; sleep 50; done ) 2>/dev/null &
      SUDO_KEEPALIVE_PID=$!
      trap 'kill $SUDO_KEEPALIVE_PID 2>/dev/null || true' EXIT
    else
      fail "sudo manquant. Installe-le ou exécute en root."
    fi
  fi
}

apt_install_base() {
  log "Mise à jour de l'index apt..."
  $SUDO apt-get update -qq
  log "Installation des dépendances système..."
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    ca-certificates curl gnupg lsb-release \
    git openssl jq \
    python3 python3-venv python3-pip \
    apt-transport-https software-properties-common \
    >/dev/null
  ok "Dépendances de base installées"
}

apt_install_node() {
  if command -v node >/dev/null 2>&1 && node -v 2>/dev/null | grep -qE '^v(20|22|24)'; then
    ok "Node.js $(node -v) déjà présent"
    return
  fi
  log "Installation de Node.js 20 LTS (NodeSource)..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash - >/dev/null 2>&1
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs >/dev/null
  ok "Node.js $(node -v) installé"
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ',') + Compose déjà présents"
    return
  fi
  log "Installation de Docker Engine + Compose v2..."
  $SUDO install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | $SUDO gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
  local codename
  codename="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $codename stable" \
    | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
  $SUDO apt-get update -qq
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
  $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
  ok "Docker $(docker --version | awk '{print $3}' | tr -d ',') installé"
}

add_to_docker_group() {
  if [ "$EUID" -eq 0 ]; then return; fi
  if id -nG "$USER" | grep -qw docker; then
    ok "$USER déjà dans le groupe docker"
    return
  fi
  log "Ajout de $USER au groupe docker..."
  $SUDO usermod -aG docker "$USER"
  warn "Pour que ça prenne effet sans reconnexion, le script utilise sudo docker."
  USE_SUDO_DOCKER=1
}

configure_ufw() {
  if ! command -v ufw >/dev/null 2>&1; then
    return
  fi
  if ! $SUDO ufw status 2>/dev/null | grep -q "Status: active"; then
    return
  fi
  log "Configuration UFW (ports 80, 443)..."
  $SUDO ufw allow 80/tcp >/dev/null 2>&1 || true
  $SUDO ufw allow 443/tcp >/dev/null 2>&1 || true
  ok "UFW : 80 + 443 ouverts"
}

run_main_installer() {
  log "Lancement de install.sh..."
  if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git fetch --quiet origin "$BRANCH"
    git checkout --quiet "$BRANCH"
    git pull --ff-only --quiet origin "$BRANCH"
  else
    git clone --branch "$BRANCH" --depth 50 "$REPO_URL" "$INSTALL_DIR"
  fi
  if [ "${USE_SUDO_DOCKER:-0}" = "1" ]; then
    # Le user n'a pas encore les droits docker effectifs : on enveloppe
    # docker / docker compose avec sudo le temps de cette session.
    export PATH="$INSTALL_DIR/scripts/_sudo_docker_shim:$PATH"
    mkdir -p "$INSTALL_DIR/scripts/_sudo_docker_shim"
    cat > "$INSTALL_DIR/scripts/_sudo_docker_shim/docker" <<'SHIM'
#!/usr/bin/env bash
exec sudo docker "$@"
SHIM
    chmod +x "$INSTALL_DIR/scripts/_sudo_docker_shim/docker"
  fi
  bash "$INSTALL_DIR/install.sh"
}

post_install_hint() {
  cat <<EOF

${C_GREEN}══════════════════════════════════════════════════════════════════════${C_RESET}
${C_GREEN}  Installation Ubuntu terminée.${C_RESET}
${C_GREEN}══════════════════════════════════════════════════════════════════════${C_RESET}

EOF
  if [ "${USE_SUDO_DOCKER:-0}" = "1" ]; then
    cat <<EOF
  ${C_YELLOW}Important :${C_RESET} ton user vient d'être ajouté au groupe docker.
  Pour utiliser \`docker\` sans sudo, déconnecte-toi puis reconnecte-toi
  (ou redémarre la session).

EOF
  fi
}

main() {
  banner
  require_ubuntu
  require_sudo
  apt_install_base
  apt_install_node
  install_docker
  add_to_docker_group
  configure_ufw
  run_main_installer
  post_install_hint
}

main "$@"
