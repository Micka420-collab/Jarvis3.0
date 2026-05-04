#!/usr/bin/env bash
# Télécharge les modèles requis (Whisper, Piper voix fr, ECAPA SpeechBrain).
set -euo pipefail

MODELS_DIR="$(cd "$(dirname "$0")/.." && pwd)/models"
mkdir -p "$MODELS_DIR/whisper" "$MODELS_DIR/piper" "$MODELS_DIR/ecapa"

echo "→ Whisper sera téléchargé automatiquement par faster-whisper au 1er lancement."

PIPER_VOICE="${PIPER_VOICE:-fr_FR-siwis-medium}"
PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium"
echo "→ Piper voix : $PIPER_VOICE"
if [[ ! -f "$MODELS_DIR/piper/${PIPER_VOICE}.onnx" ]]; then
  curl -L -o "$MODELS_DIR/piper/${PIPER_VOICE}.onnx" "$PIPER_BASE/${PIPER_VOICE}.onnx"
  curl -L -o "$MODELS_DIR/piper/${PIPER_VOICE}.onnx.json" "$PIPER_BASE/${PIPER_VOICE}.onnx.json"
fi

echo "→ ECAPA-TDNN sera téléchargé par SpeechBrain au 1er lancement vers /models/ecapa"

echo "✅ Modèles prêts dans $MODELS_DIR"
