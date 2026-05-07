# Politique de sécurité

Merci de prendre la sécurité de Jarvis 3.0 au sérieux. Si tu as découvert une vulnérabilité, **ne l'ouvre pas en issue publique**.

## Versions supportées

| Version | Statut |
|---------|--------|
| 0.1.x   | ✅ supportée |
| < 0.1   | ❌ non supportée |

## Reporter une vulnérabilité

### Voie privilégiée : GitHub Security Advisory

1. Va sur la page [Security](https://github.com/Micka420-collab/Jarvis3.0/security/advisories/new) du repo
2. Clique **"Report a vulnerability"**
3. Remplis le formulaire (description, impact, reproduction, mitigation)

GitHub te garantit la confidentialité jusqu'à publication.

### Voie alternative : email

`security@jarvis-project.org` (à configurer — pour l'instant, ouvre un advisory)

Inclus :
- **Description** de la vuln
- **Impact** (qui est touché, quoi compromis)
- **Steps to reproduce** détaillés
- **Versions affectées** (commit SHA si possible)
- **Mitigation** proposée si tu en as une

## Délais d'engagement

| Phase | Délai cible |
|-------|-------------|
| Acknowledgment | 48h |
| Investigation initiale | 7 jours |
| Patch + advisory publié | 30 jours (90 jours max pour les vulns complexes) |

## Périmètre

**In scope** :
- Code des services dans `services/`
- Frontend `frontend/`
- Scripts d'installation `install*.sh`, `scripts/`
- Configuration Docker / Helm fournie
- Wizards et endpoints admin

**Hors scope** (à reporter directement aux mainteneurs concernés) :
- Vulnérabilités dans Anthropic / OpenAI / OpenRouter (→ leurs propres programmes)
- Bugs Home Assistant (→ HA Foundation)
- CVEs upstream Docker / Postgres / Redis (→ leurs canaux)

## Bonnes pratiques en self-host

Pour les utilisateurs Jarvis :

- **Ne PAS exposer** Jarvis directement sur Internet sans VPN (Tailscale, WireGuard)
- Utiliser **TLS valide** (Let's Encrypt) en prod, pas le cert auto-signé
- **Faire pivoter** régulièrement `JWT_SECRET`, `POSTGRES_PASSWORD`
- **Backup chiffré** : `gpg` sur les tarballs `scripts/backup.sh`
- **Activer fail2ban** : voir [`docs/operations.md`](../docs/operations.md)
- **Restrict ingress** : Traefik allowlist sur les routes admin
- **Ne PAS commit** `.env` en clair (déjà dans `.gitignore`)

## Hall of Fame

Les chercheurs qui ont reporté des vulnérabilités responsablement seront crédités ici (avec leur accord) :

_(personne pour l'instant — fais-toi connaître !)_

## Récompenses

Pas de bug bounty payant pour l'instant (projet communautaire), mais :
- Crédit dans l'advisory et la release notes
- Mention dans le hall of fame
- Sticker / goodies si tu nous donnes une adresse 🎁
