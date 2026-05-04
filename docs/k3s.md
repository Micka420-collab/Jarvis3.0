# Déploiement Kubernetes (k3s)

Alternative à Docker Compose pour déployer Jarvis sur un cluster k3s (single-node ou HA).

## Prérequis

- k3s installé (mode single-node : `curl -sfL https://get.k3s.io | sh -`)
- `kubectl` configuré (`sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config`)
- `kubectl kustomize` ou `kubectl apply -k` (kustomize embarqué)
- Une StorageClass par défaut (k3s en fournit une : `local-path`)
- Images des microservices publiées sur un registre accessible (GHCR, Harbor, registre privé)

## Build & push des images

```bash
# Connexion à GHCR (token avec scope write:packages)
echo "$GHCR_PAT" | docker login ghcr.io -u <user> --password-stdin

# Build multi-arch (amd64 + arm64) avec buildx
docker buildx create --use --name jarvis-builder

for s in gateway voice llm orchestrator memory iot security vision; do
  docker buildx build --platform linux/amd64,linux/arm64 \
    -t ghcr.io/micka420-collab/jarvis-$s:v0.1.0 \
    --push services/$s
done

docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/micka420-collab/jarvis-frontend:v0.1.0 --push frontend
```

## Déploiement prod (x86_64)

```bash
# 1. Configurer les secrets (à faire UNE FOIS, jamais commiter)
kubectl create namespace jarvis
kubectl create secret generic jarvis-secrets \
  --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..." \
  --from-literal=ARGUS_API_TOKEN="..." \
  --from-literal=MQTT_PASSWORD="$(openssl rand -hex 12)" \
  -n jarvis

# 2. Appliquer l'overlay prod
kubectl apply -k k8s/overlays/prod

# 3. Suivre le rollout
kubectl get pods -n jarvis -w
kubectl logs -n jarvis -l app=gateway --tail=100 -f
```

## Déploiement Raspberry Pi (ARM64)

```bash
kubectl apply -k k8s/overlays/rpi
```

L'overlay rpi force :
- 1 seul replica par service
- Modèles légers (Whisper `tiny`, Llama 3.2 `1b`, voix Piper `low`)
- Vision désactivée (Frigate trop lourd sans Coral USB)

Voir [docs/raspberry-pi.md](raspberry-pi.md) pour les notes spécifiques au matériel.

## Accès

- L'Ingress route `https://jarvis.local` vers le frontend, et `/api`, `/ws` vers le gateway.
- Pour LAN sans DNS, ajoute dans `/etc/hosts` : `<IP-K3S> jarvis.local`.

## TLS

k3s embarque Traefik. Deux options :
- **Self-signed** (par défaut, valable LAN) : aucune action.
- **cert-manager + Let's Encrypt DNS challenge** :
  ```bash
  kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
  # puis ClusterIssuer Let's Encrypt + annotation cert-manager.io/cluster-issuer sur l'Ingress
  ```

## Persistance

PVCs par défaut : 1 Gi (Redis, Mosquitto), 5 Gi (Postgres, Qdrant), 10 Gi (models PVC partagé voice + vision).
Sauvegardes recommandées via `velero`, ou rsync simple sur le host k3s (`/var/lib/rancher/k3s/storage/`).

## Mise à l'échelle

```bash
kubectl -n jarvis scale deploy/gateway --replicas=3
kubectl -n jarvis scale deploy/orchestrator --replicas=3
```

Le service voice ne se scale pas horizontalement par défaut (sticky session WS). Pour le scaler, ajouter une `session-affinity: ClientIP` sur le Service ou utiliser un broker externe pour la session.

## Désinstaller

```bash
kubectl delete -k k8s/overlays/prod
kubectl delete pvc --all -n jarvis        # ATTENTION : perte des données
kubectl delete namespace jarvis
```
