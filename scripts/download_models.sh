#!/usr/bin/env bash
# Télécharge les modèles requis (Whisper, Piper voix fr, ECAPA SpeechBrain).
set -euo pipefail

MODELS_DIR="$(cd "$(dirname "$0")/.." && pwd)/models"
mkdir -p "$MODELS_DIR/whisper" "$MODELS_DIR/piper" "$MODELS_DIR/ecapa"

echo "→ Whisper sera téléchargé automatiquement par faster-whisper au 1er lancement."

PIPER_VOICE="${PIPER_VOICE:-fr_FR-siwis-medium}"
# format: <lang>_<COUNTRY>-<speaker>-<quality>
# extraction de la quality (low|medium|high|x_low) à partir du nom
PIPER_QUALITY="${PIPER_VOICE##*-}"
PIPER_REST="${PIPER_VOICE%-*}"          # ex: fr_FR-siwis
PIPER_SPEAKER="${PIPER_REST##*-}"       # ex: siwis
PIPER_LANG="${PIPER_REST%-*}"           # ex: fr_FR
PIPER_LANG_FAMILY="${PIPER_LANG%%_*}"   # ex: fr
PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/${PIPER_LANG_FAMILY}/${PIPER_LANG}/${PIPER_SPEAKER}/${PIPER_QUALITY}"
echo "→ Piper voix : $PIPER_VOICE  ($PIPER_BASE)"
if [[ ! -f "$MODELS_DIR/piper/${PIPER_VOICE}.onnx" ]]; then
  curl -fL -o "$MODELS_DIR/piper/${PIPER_VOICE}.onnx" "$PIPER_BASE/${PIPER_VOICE}.onnx" \
    || { echo "  ⚠️  échec download $PIPER_VOICE" ; rm -f "$MODELS_DIR/piper/${PIPER_VOICE}.onnx" ; }
  curl -fL -o "$MODELS_DIR/piper/${PIPER_VOICE}.onnx.json" "$PIPER_BASE/${PIPER_VOICE}.onnx.json" \
    || { echo "  ⚠️  échec download ${PIPER_VOICE}.onnx.json" ; rm -f "$MODELS_DIR/piper/${PIPER_VOICE}.onnx.json" ; }
fi

echo "→ ECAPA-TDNN sera téléchargé par SpeechBrain au 1er lancement vers /models/ecapa"

# --- AASIST anti-spoofing (optionnel) ---
# L'URL par défaut pointe sur un repo HF qui peut nécessiter une auth.
# Skip silencieusement si la variable AASIST_URL n'est pas explicitement fournie
# par l'utilisateur (le service vision tourne très bien sans liveness check).
mkdir -p "$MODELS_DIR/aasist"
if [[ -n "${AASIST_URL:-}" && ! -f "$MODELS_DIR/aasist/aasist.onnx" ]]; then
  echo "→ AASIST anti-deepfake : $AASIST_URL"
  if curl -fsSL -o "$MODELS_DIR/aasist/aasist.onnx" "$AASIST_URL" 2>/dev/null; then
    echo "  ✅ AASIST téléchargé"
  else
    rm -f "$MODELS_DIR/aasist/aasist.onnx"
    echo "  ⚠️  AASIST non téléchargé — liveness désactivée (export AASIST_URL=... pour réessayer)"
  fi
fi

echo "✅ Modèles prêts dans $MODELS_DIR"
