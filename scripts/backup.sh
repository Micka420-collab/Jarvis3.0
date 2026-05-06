#!/usr/bin/env bash
# Backup atomique de l'état Jarvis : Postgres + Qdrant + Redis + .env + speakers.yaml
#
#   ./scripts/backup.sh            → backups/jarvis-YYYY-MM-DD-HHMMSS.tar.gz
#   ./scripts/backup.sh --keep 7   → garde les 7 derniers, supprime le reste
#   ./scripts/backup.sh --remote user@nas:/srv/jarvis-backups   → rsync vers NAS

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

KEEP=14
REMOTE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP="$2"; shift 2 ;;
    --remote) REMOTE="$2"; shift 2 ;;
    *) echo "usage: $0 [--keep N] [--remote dst]" >&2; exit 1 ;;
  esac
done

STAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"
DIR="backups/jarvis-$STAMP"
mkdir -p "$DIR"

log() { printf "→ %s\n" "$*"; }

log "Postgres dump..."
docker compose exec -T postgres pg_dumpall -U jarvis | gzip > "$DIR/postgres.sql.gz"

log "Qdrant snapshot..."
docker compose exec -T qdrant sh -c 'curl -fsS -X POST http://localhost:6333/snapshots' \
  > "$DIR/qdrant-snapshot.json" || true
# Le binaire qdrant écrit le snapshot dans /qdrant/snapshots, on le récupère :
docker compose cp qdrant:/qdrant/snapshots/. "$DIR/qdrant-snapshots/" 2>/dev/null || true

log "Redis dump..."
docker compose exec -T redis sh -c 'redis-cli SAVE > /dev/null && cat /data/dump.rdb' \
  > "$DIR/redis-dump.rdb" || true

log "Configs..."
cp .env "$DIR/.env" 2>/dev/null || true
cp services/voice/app/speakers.yaml "$DIR/speakers.yaml" 2>/dev/null || true
cp -r config "$DIR/config" 2>/dev/null || true

log "Compression..."
tar -czf "${DIR}.tar.gz" -C backups "jarvis-$STAMP"
rm -rf "$DIR"
echo "✓ ${DIR}.tar.gz ($(du -h "${DIR}.tar.gz" | cut -f1))"

# Rétention
if [ "$KEEP" -gt 0 ]; then
  log "Rétention : on garde les $KEEP plus récents"
  ls -1t backups/jarvis-*.tar.gz 2>/dev/null \
    | tail -n +$((KEEP + 1)) \
    | xargs -r rm -v
fi

# Sync distant
if [ -n "$REMOTE" ]; then
  log "rsync → $REMOTE"
  rsync -av --delete "backups/" "$REMOTE/"
fi

echo "✅ Backup terminé."
