#!/usr/bin/env bash
# Restore depuis un tarball produit par backup.sh
#   ./scripts/restore.sh backups/jarvis-2026-05-06T123000Z.tar.gz

set -euo pipefail
ARCHIVE="${1:-}"
[ -f "$ARCHIVE" ] || { echo "usage: $0 <backup.tar.gz>"; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "→ Extraction $ARCHIVE..."
tar -xzf "$ARCHIVE" -C "$WORK"
SRC="$(ls -d "$WORK"/jarvis-* | head -1)"

read -r -p "⚠ Cela va ÉCRASER la base actuelle. Continuer ? [o/N] " ans
[[ "$ans" =~ ^[OoYy]$ ]] || { echo "Annulé."; exit 0; }

echo "→ Postgres..."
docker compose up -d postgres
sleep 3
gunzip -c "$SRC/postgres.sql.gz" | docker compose exec -T postgres psql -U jarvis

echo "→ Redis..."
docker compose stop redis 2>/dev/null || true
docker compose cp "$SRC/redis-dump.rdb" redis:/data/dump.rdb 2>/dev/null || true
docker compose start redis 2>/dev/null || true

if [ -d "$SRC/qdrant-snapshots" ]; then
  echo "→ Qdrant snapshots (restore manuelle via UI/API recommandée)..."
  docker compose cp "$SRC/qdrant-snapshots/." qdrant:/qdrant/snapshots/ 2>/dev/null || true
fi

echo "→ .env / speakers.yaml..."
cp "$SRC/.env" .env 2>/dev/null || true
cp "$SRC/speakers.yaml" services/voice/app/speakers.yaml 2>/dev/null || true

echo "✅ Restauré. Relance : docker compose up -d --force-recreate"
