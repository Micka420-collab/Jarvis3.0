#!/usr/bin/env bash
# Vérifie que tous les services Jarvis répondent.
set -e
echo "→ gateway"
curl -fsS http://localhost:8000/api/health
echo
echo "→ llm"
docker compose exec -T llm curl -fsS http://localhost:8000/health
echo
echo "→ orchestrator"
docker compose exec -T orchestrator curl -fsS http://localhost:8001/health
echo
echo "→ memory"
docker compose exec -T memory curl -fsS http://localhost:8004/health
echo
echo "→ iot"
docker compose exec -T iot curl -fsS http://localhost:8002/health
echo
echo "→ security"
docker compose exec -T security curl -fsS http://localhost:8003/health
echo
echo "✅ tous up"
