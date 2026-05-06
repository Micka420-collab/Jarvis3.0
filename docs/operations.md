# Opérations : monitoring, backup, sécurité

## Backup

```bash
make backup                                     # → backups/jarvis-<stamp>.tar.gz
./scripts/backup.sh --keep 30                   # garde les 30 derniers
./scripts/backup.sh --remote user@nas:/srv/jb   # rsync vers NAS
```

Cron quotidien (3h du matin, garde 30 jours, rsync NAS) :
```cron
0 3 * * * cd /home/$USER/Jarvis3.0 && bash scripts/backup.sh --keep 30 --remote backup@nas:/srv/jarvis-bak >> /var/log/jarvis-backup.log 2>&1
```

Restore :
```bash
./scripts/restore.sh backups/jarvis-2026-05-06T030000Z.tar.gz
docker compose up -d --force-recreate
```

## Monitoring

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

Stack : **Prometheus + Grafana + Loki + Promtail + cAdvisor + Node Exporter**.

Accès :
- Grafana : `https://grafana.jarvis.local` (admin / `GRAFANA_ADMIN_PASSWORD`)
- Prometheus : `https://prometheus.jarvis.local`

Le dashboard "Jarvis · Overview" est provisionné automatiquement avec :
- Containers UP, CPU/RAM par service, logs Loki par container

Pour exposer `/metrics` depuis tes services Python, ajoute à chaque app :
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

## Rate limiting (Traefik)

Activé par défaut sur le `gateway` :
- 60 req/s en moyenne, burst 120
- HSTS + frame-deny + X-Content-Type-Options + Referrer-Policy stricte

Override dans `docker-compose.override.yml` :
```yaml
services:
  gateway:
    labels:
      - traefik.http.middlewares.gateway-ratelimit.ratelimit.average=120
      - traefik.http.middlewares.gateway-ratelimit.ratelimit.burst=240
```

## fail2ban

Sur l'hôte :
```bash
sudo apt install fail2ban
sudo cp infra/fail2ban/jail.local /etc/fail2ban/jail.d/jarvis.conf
sudo cp infra/fail2ban/filter.d/jarvis-auth.conf /etc/fail2ban/filter.d/
sudo systemctl restart fail2ban
sudo fail2ban-client status jarvis-auth
```

Bans automatiques :
- 5 logins KO en 5 min → ban 1 h
- 3 admin failures en 10 min → ban 24 h

## Tests CI

GitHub Actions sur push/PR (`.github/workflows/ci.yml`) :
- `python` : ast.parse + ruff + pytest
- `shell` : shellcheck + bash -n
- `yaml` : compose + helm lint
- `docker-build` : smoke build du gateway
- `frontend` : npm run build

Lance localement :
```bash
pytest -q tests/
ruff check services/
shellcheck install*.sh scripts/*.sh
```

## Sécurité

- ✅ JWT signés HS256
- ✅ Voix-print ECAPA + AASIST liveness optionnel
- ✅ Rate limiting Traefik + fail2ban
- ✅ HSTS + headers sécurité
- ✅ Audit complet `reasoning_traces` (qui a fait quoi)
- ⚠️ Reverse proxy = TLS auto-signé en LAN (utilise Let's Encrypt + DNS challenge pour un vrai cert)
- ⚠️ Postgres password en clair dans `.env` (à migrer vers Docker secrets / sealed-secrets en k8s)

## Fédération multi-instances

Voir [`docs/federation.md`](federation.md).
