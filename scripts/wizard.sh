#!/usr/bin/env bash
# Wizard de connexion des features à Jarvis.
#
# Lancé automatiquement à la fin de install.sh, ou à la demande :
#   cd ~/Jarvis3.0 && make wizard
#
# Sections (toutes skippables avec [n]) :
#   1. LLM (Anthropic Claude / Ollama local / Mistral)
#   2. Home Assistant (URL + long-lived token + test)
#   3. Zigbee2MQTT (port série + profile docker)
#   4. Z-Wave via zwave-js-ui
#   5. Caméras Frigate (URL + clips)
#   6. Argus (alertes réseau)
#   7. Push notifications (VAPID — généré, juste un check)
#   8. Multi-room audio (édition speakers.yaml)
#   9. Agents externes (Hermes / OpenClaw)
#  10. Enrôlement voix-print
#  11. Tests de connexion finaux

set -euo pipefail

INSTALL_DIR="${JARVIS_INSTALL_DIR:-$HOME/Jarvis3.0}"
ENV_FILE="$INSTALL_DIR/.env"
COMPOSE="docker compose"

C_BLUE="\033[1;34m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_DIM="\033[2m"
C_RESET="\033[0m"

cd "$INSTALL_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Pas de .env. Lance d'abord install.sh."
  exit 1
fi

# ---------- helpers ----------

step()  { printf "\n${C_BLUE}══${C_RESET} ${C_BLUE}%s${C_RESET}\n" "$*"; }
ok()    { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn()  { printf "${C_YELLOW}!${C_RESET} %s\n" "$*"; }
ask()   {
  local prompt="$1"; local default="${2:-}"; local out
  if [ -n "$default" ]; then
    read -r -p "$(printf "${C_DIM}%s${C_RESET} [%s] " "$prompt" "$default")" out </dev/tty || true
  else
    read -r -p "$(printf "${C_DIM}%s${C_RESET} " "$prompt")" out </dev/tty || true
  fi
  printf "%s" "${out:-$default}"
}
confirm() {
  local prompt="$1"; local default="${2:-O/n}"; local out
  read -r -p "$(printf "${C_DIM}%s${C_RESET} [%s] " "$prompt" "$default")" out </dev/tty || true
  out="${out:-${default%%/*}}"
  [[ "$out" =~ ^[OoYy]$ ]]
}
set_env() {
  local key="$1"; local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
  rm -f "${ENV_FILE}.bak"
}
get_env() { grep "^${1}=" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2- || true; }

# ---------- sections ----------

banner() {
  cat <<'EOF'

   ███████╗  Jarvis 3.0 · Wizard de connexion
   Connecte un par un tes services à l'IA.
   À chaque étape : Entrée pour skip, ou tape la valeur.

EOF
}

section_llm() {
  step "1/11 · LLM (cerveau de Jarvis)"
  echo "   1) Anthropic Claude (cloud, recommandé qualité)"
  echo "   2) Ollama (local, sans cloud)"
  echo "   3) Mistral (cloud, alternative européenne)"
  echo "   0) Skip"
  local ch
  ch="$(ask "Choix ?" "1")"
  case "$ch" in
    1)
      local key model
      key="$(ask "Clé API Anthropic (sk-ant-...)" "$(get_env ANTHROPIC_API_KEY)")"
      model="$(ask "Modèle" "claude-sonnet-4-6")"
      set_env LLM_PROVIDER anthropic
      set_env ANTHROPIC_API_KEY "$key"
      set_env LLM_MODEL "$model"
      ok "Anthropic configuré"
      ;;
    2)
      local model
      model="$(ask "Modèle Ollama" "llama3.1:8b")"
      set_env LLM_PROVIDER ollama
      set_env LLM_MODEL "$model"
      if confirm "Pull '$model' maintenant ?" "O/n"; then
        $COMPOSE --profile ollama up -d ollama 2>/dev/null || warn "ollama profile non actif"
        $COMPOSE exec -T ollama ollama pull "$model" || warn "pull a échoué"
      fi
      ok "Ollama configuré"
      ;;
    3)
      local key
      key="$(ask "Clé API Mistral" "$(get_env MISTRAL_API_KEY)")"
      set_env LLM_PROVIDER mistral
      set_env MISTRAL_API_KEY "$key"
      ok "Mistral configuré"
      ;;
    *) warn "Skip" ;;
  esac
}

section_homeassistant() {
  step "2/11 · Home Assistant"
  if ! confirm "Connecter à un Home Assistant existant ?" "O/n"; then warn "Skip"; return; fi
  local url token
  url="$(ask "URL HA" "$(get_env HA_BASE_URL)")"
  token="$(ask "Long-lived access token" "$(get_env HA_LONG_LIVED_TOKEN)")"
  set_env HA_BASE_URL "$url"
  set_env HA_LONG_LIVED_TOKEN "$token"
  if curl -fsS -H "Authorization: Bearer $token" "$url/api/" >/dev/null 2>&1; then
    ok "Connexion HA validée"
  else
    warn "Connexion HA NON validée — vérifie URL/token"
  fi
}

section_zigbee() {
  step "3/11 · Zigbee2MQTT"
  if ! confirm "Activer Zigbee2MQTT ?" "n/O"; then warn "Skip"; return; fi
  local port
  port="$(ask "Adapter Zigbee (ex: /dev/ttyUSB0 ou /dev/ttyACM0)" "/dev/ttyACM0")"
  set_env ZIGBEE_ADAPTER "$port"
  set_env COMPOSE_PROFILES "$(get_env COMPOSE_PROFILES),zigbee" 2>/dev/null || set_env COMPOSE_PROFILES "zigbee"
  ok "Zigbee2MQTT activé. Lance : docker compose --profile zigbee up -d zigbee2mqtt"
}

section_zwave() {
  step "4/11 · Z-Wave (zwave-js-ui)"
  if ! confirm "Activer Z-Wave ?" "n/O"; then warn "Skip"; return; fi
  local port
  port="$(ask "Adapter Z-Wave (ex: /dev/ttyUSB-zwave)" "/dev/ttyUSB-zwave")"
  set_env ZWAVE_ADAPTER "$port"
  ok "zwave-js-ui activé. UI sur https://zwave.\$JARVIS_DOMAIN après : docker compose --profile zwave up -d zwave-js-ui"
}

section_cameras() {
  step "5/11 · Caméras (Frigate)"
  if ! confirm "Tu utilises Frigate pour les caméras ?" "n/O"; then warn "Skip"; return; fi
  local url
  url="$(ask "URL Frigate" "http://frigate:5000")"
  set_env FRIGATE_API_URL "$url"
  ok "Frigate connecté pour Claude Vision"
}

section_argus() {
  step "6/11 · Argus (alertes réseau)"
  if ! confirm "Connecter à Argus ?" "n/O"; then warn "Skip"; return; fi
  local url token
  url="$(ask "URL Argus" "http://argus:9000")"
  token="$(ask "Token API Argus" "$(get_env ARGUS_API_TOKEN)")"
  set_env ARGUS_BASE_URL "$url"
  set_env ARGUS_API_TOKEN "$token"
  ok "Argus connecté"
}

section_push() {
  step "7/11 · Push notifications (Web Push)"
  if [ -n "$(get_env VAPID_PUBLIC_KEY)" ]; then
    ok "Clés VAPID déjà générées (skip)"
  else
    if command -v node >/dev/null 2>&1; then
      local v pub priv
      v="$(npx -y -q web-push generate-vapid-keys --json 2>/dev/null || true)"
      pub="$(echo "$v" | python3 -c 'import sys,json;print(json.load(sys.stdin)["publicKey"])' 2>/dev/null || echo "")"
      priv="$(echo "$v" | python3 -c 'import sys,json;print(json.load(sys.stdin)["privateKey"])' 2>/dev/null || echo "")"
      if [ -n "$pub" ]; then
        set_env VAPID_PUBLIC_KEY "$pub"
        set_env VAPID_PRIVATE_KEY "$priv"
        ok "Clés VAPID générées"
      fi
    else
      warn "Node.js manquant — push désactivé"
    fi
  fi
}

section_multiroom() {
  step "8/11 · Multi-room audio"
  if ! confirm "Configurer des enceintes par pièce ?" "n/O"; then warn "Skip"; return; fi
  echo "Édite manuellement : services/voice/app/speakers.yaml"
  echo "Exemples kind=browser/mqtt/snapcast/homeassistant"
  if confirm "Ouvrir l'éditeur maintenant ?" "n/O"; then
    "${EDITOR:-nano}" "$INSTALL_DIR/services/voice/app/speakers.yaml" </dev/tty
  fi
  ok "speakers.yaml prêt — recharger : docker compose restart voice"
}

section_agents() {
  step "9/11 · Agents externes (Hermes / OpenClaw)"
  if ! confirm "Activer la délégation à Hermes/OpenClaw ?" "n/O"; then warn "Skip"; return; fi
  if confirm "Installer les agents dans l'image Docker (lourd, ~1 Go) ?" "n/O"; then
    set_env INSTALL_HERMES true
    set_env INSTALL_OPENCLAW true
    $COMPOSE build agents
  else
    echo "Mode host : installe sur ton poste"
    echo "  curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash"
    echo "  curl -fsSL https://openclaw.ai/install.sh | bash"
  fi
  $COMPOSE up -d agents
  ok "Agents activés"
}

section_voice() {
  step "10/11 · Enrôlement voix-print (owner)"
  if ! confirm "Enrôler ta voix maintenant ?" "O/n"; then warn "Skip"; return; fi
  if [ -x "$INSTALL_DIR/scripts/enroll_voice.sh" ]; then
    bash "$INSTALL_DIR/scripts/enroll_voice.sh"
  else
    warn "Script enroll_voice.sh non trouvé — utilise l'admin /admin → Membres"
  fi
}

section_tests() {
  step "11/11 · Tests de connexion finaux"
  $COMPOSE up -d
  sleep 3
  local ok_n=0 ko_n=0
  for svc in gateway orchestrator memory iot security voice; do
    if $COMPOSE exec -T "$svc" curl -fsS http://localhost:8000/health >/dev/null 2>&1 \
       || $COMPOSE exec -T "$svc" curl -fsS http://localhost:8001/health >/dev/null 2>&1 \
       || $COMPOSE exec -T "$svc" curl -fsS http://localhost:8002/health >/dev/null 2>&1 \
       || $COMPOSE exec -T "$svc" curl -fsS http://localhost:8003/health >/dev/null 2>&1 \
       || $COMPOSE exec -T "$svc" curl -fsS http://localhost:8004/health >/dev/null 2>&1; then
      ok "$svc OK"; ok_n=$((ok_n+1))
    else
      warn "$svc KO"; ko_n=$((ko_n+1))
    fi
  done
  echo
  echo "Résumé : ${ok_n} services OK, ${ko_n} KO"
}

# ---------- main ----------

banner
section_llm
section_homeassistant
section_zigbee
section_zwave
section_cameras
section_argus
section_push
section_multiroom
section_agents

# redémarre les services pour charger les nouvelles env vars
step "Redémarrage des services pour appliquer la config…"
$COMPOSE up -d --force-recreate gateway orchestrator iot security agents 2>/dev/null || true

section_voice
section_tests

cat <<EOF

${C_GREEN}══════════════════════════════════════════════════════════════════════${C_RESET}
${C_GREEN}  Configuration terminée.${C_RESET}
${C_GREEN}══════════════════════════════════════════════════════════════════════${C_RESET}

  Web :     https://$(get_env JARVIS_DOMAIN)
  Admin :   https://$(get_env JARVIS_DOMAIN)/admin
  Logs :    cd $INSTALL_DIR && make logs
  Re-run :  make wizard

EOF
