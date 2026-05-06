# Fédération multi-instances

Permet d'avoir plusieurs instances Jarvis qui se synchronisent : résidence principale ↔ secondaire ↔ instance mobile.

## Cas d'usage

- **2 maisons** : tu déménages entre la principale et la secondaire ; ton historique vocal, tes routines, tes membres te suivent.
- **Mode mobile** : une instance Jarvis sur ton laptop synchronise avec celle de la maison via VPN.
- **Failover** : si l'instance principale tombe, une instance secondaire prend le relais.

## Architecture (v0.1)

```
   Instance "primary"            Instance "secondary"
   ┌────────────────┐            ┌────────────────┐
   │  federation    │ ◄────────► │  federation    │
   │  :8006         │  HTTPS     │  :8006         │
   └────┬───────────┘  + JWT     └────┬───────────┘
        │                              │
        │ pub/sub federation.*         │
        ▼                              ▼
     Redis (local)                  Redis (local)
```

Chaque instance :
- a un `INSTANCE_ID` unique (généré ou défini)
- un `INSTANCE_LABEL` ("primary", "secondary", "mobile")
- une liste de `PEERS` URL connus
- envoie un heartbeat toutes les 30 s aux peers

## Configuration

`.env` sur chaque instance :

```env
FEDERATION_INSTANCE_ID=primary-paris    # nom court, stable
FEDERATION_LABEL=primary
FEDERATION_PEERS=https://jarvis.bordeaux.local,https://jarvis-mobile.tailscale.net
FEDERATION_HEARTBEAT_S=30
```

## État implémenté (v0.1)

- ✅ Service skeleton FastAPI (`services/federation/`)
- ✅ Heartbeat pub/sub local + push HTTP aux peers
- ✅ `GET /health`, `GET /peers`, `POST /heartbeat`

## À implémenter (v0.2+)

- [ ] **Catalog sync** : devices, routines, users (préfixés par `instance_id`)
- [ ] **Memory share** : Qdrant collection partagée pour souvenirs globaux
- [ ] **Forwarding** : si un device n'est pas trouvé localement, demander aux peers
- [ ] **mTLS** : auth mutuelle entre peers via certificats
- [ ] **Conflict resolution** : pour les routines éditées en parallèle
- [ ] **Bandwidth-aware** : sync delta avec compression

## Sécurité

- mTLS prévu (v0.2) — entre temps : VPN obligatoire (Tailscale, WireGuard)
- Token JWT signé par la clé maître pour chaque appel inter-instance
- Whitelist `FEDERATION_PEERS` stricte (refus des appels non listés)
- Pas de propagation de secrets : `ANTHROPIC_API_KEY` reste local
