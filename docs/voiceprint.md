# Voix-print créateur

Authentification biométrique vocale pour réserver les commandes admin (porte garage, désarmer Argus…) au seul créateur.

## Modèle

- **ECAPA-TDNN** (SpeechBrain `spkrec-ecapa-voxceleb`)
- Embedding 192 dimensions, L2-normalisé
- Stocké en `pgvector` (`voiceprints.embedding vector(192)`)

## Enrôlement

```bash
make enroll-voice
# (équivalent à : docker compose exec voice python /app/scripts/enroll_voiceprint.py --user $OWNER --owner)
```

5 phrases ~4s chacune. La moyenne L2-normalisée est stockée. Refaire l'enrôlement tous les 6 mois ou après un rhume prolongé.

## Vérification runtime

À chaque utterance >1s, le service voice extrait l'embedding et calcule la similarité cosine vs l'embedding owner.

| Score | Action |
|---|---|
| ≥ 0.75 | accepté (owner) |
| 0.65–0.75 | zone grise → challenge phrase obligatoire |
| < 0.65 | rejet (utilisateur inconnu) |

## Anti-deepfake / replay

1. **Challenge phrase** dynamique : pour les commandes admin, l'orchestrator génère une phrase aléatoire (`"dis: bleu-marin-quatorze"`). Le transcript doit matcher ET l'embedding doit valider.
2. **Cooldown** : 1 commande admin maximum toutes les 30s (`ADMIN_COMMAND_COOLDOWN_SECONDS`).
3. **Liveness AASIST** (option à activer) : détecte les voix synthétisées via prosodie.
4. **Audit** : chaque vérification est loggée dans `auth_events` (Postgres).

## Code de référence

- Engine : `services/voice/app/voiceprint.py`
- Helper gating : `services/gateway/app/auth.py:require_owner_voice`
- Schéma événement : `services/_shared/events.py:VoiceIdentityVerified`
- Script d'enrôlement : `scripts/enroll_voiceprint.py`
- Schéma SQL : `infra/postgres/init.sql` (table `voiceprints`)
