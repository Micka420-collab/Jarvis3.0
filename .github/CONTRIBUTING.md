# Contribuer à Jarvis 3.0

Merci de t'intéresser à Jarvis ! Ce projet vit grâce aux contributeurs comme toi.

Avant de commencer, lis [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Toute participation implique son acceptation.

## Sommaire

- [Façons de contribuer](#façons-de-contribuer)
- [Setup dev en 3 minutes](#setup-dev-en-3-minutes)
- [Workflow git](#workflow-git)
- [Style de code](#style-de-code)
- [Tests](#tests)
- [Commit messages](#commit-messages)
- [Documentation](#documentation)
- [Bonnes pratiques sécurité](#bonnes-pratiques-sécurité)
- [Reviews](#reviews)
- [Aide](#aide)

## Façons de contribuer

Tu peux contribuer **sans coder une ligne** :

- 🐛 **Reporter un bug** via [bug report](.github/ISSUE_TEMPLATE/bug_report.yml)
- 💡 **Proposer une feature** via [feature request](.github/ISSUE_TEMPLATE/feature_request.yml)
- 📚 **Améliorer la doc** : typos, ajouts, exemples (PR direct, pas besoin d'issue)
- 🌍 **Traduire** : actuellement FR, l'EN serait utile
- 🎨 **Améliorer l'UI** : screenshots, dashboards Grafana, thèmes
- 💬 **Aider sur les Discussions** : répondre aux questions des autres
- 📦 **Skills / agents** : partage tes plugins (cf. [`docs/skills.md`](../docs/skills.md))
- 🧪 **Tester sur ton matos** : Pi, NUC, Mac M-series, Z-Wave/Zigbee, retours bienvenus

## Setup dev en 3 minutes

```bash
# 1. Fork puis clone
git clone https://github.com/<TON-USERNAME>/Jarvis3.0.git
cd Jarvis3.0

# 2. Branche à partir de main
git checkout main && git pull origin main
git checkout -b feat/ma-feature

# 3. Lance la stack
cp .env.example .env
docker compose up -d

# 4. Pour les tests locaux
pip install pytest pytest-asyncio httpx pyyaml ruff
pytest -q

# 5. Pour le frontend
cd frontend && npm install && npm run dev
```

## Workflow git

1. **Fork** le repo sur ton compte
2. **Branche** depuis `main` : `feat/...`, `fix/...`, `docs/...`, `chore/...`
3. **Commit** avec un message clair (cf. ci-dessous)
4. **Push** sur ta branche fork
5. **Pull Request** vers `main` avec le template fourni
6. **CI doit passer** (Python tests, shell lint, YAML, frontend build)
7. **Review** par un maintainer puis merge

Branches protégées : `main` n'accepte que des PRs reviewées avec CI verte.

## Style de code

### Python

- **Python 3.11+**
- `ruff check` doit passer (config dans `pyproject.toml`)
- Type hints sur les signatures publiques
- Docstrings courts pour les fonctions non triviales (le **pourquoi**, pas le **quoi**)
- Pas de `print` en prod : `logging.getLogger(__name__)`
- Async/await partout dans les services FastAPI

### TypeScript / React

- Strict mode activé (cf. `frontend/tsconfig.json`)
- Pas de `any` sans justification (préfère `unknown`)
- Composants fonctionnels + hooks, pas de classes
- `prettier --write src` avant commit

### Shell

- `shellcheck -S error` doit passer
- `set -euo pipefail` en haut de chaque script

### YAML / Compose / Helm

- Indentation 2 espaces
- Pas de tabs
- Commentaires au-dessus des sections, pas en bout de ligne

## Tests

Chaque PR qui ajoute du comportement doit ajouter des tests. Voir `tests/` pour des exemples :

```bash
# Tests unitaires Python
pytest -q

# Test ciblé
pytest -q tests/test_autonomous.py -k "max_steps"

# Frontend
cd frontend && npm test  # à venir, pour l'instant : npm run build doit passer

# E2E (besoin de la stack docker)
make e2e-phase1
```

Couverture minimum visée : **70%** sur les modules métier.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org) :

```
<type>(<scope>): <description courte>

[corps optionnel]

[footer]
```

**Types** : `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

Exemples :
```
feat(orchestrator): support OpenRouter pour 200+ modèles
fix(voice): TTS coupe la synthèse au barge-in
docs(integrations): ajoute la section Z-Wave
chore(ci): bump pytest 8.3.0 → 8.3.3
```

Garde le sujet < 70 caractères. Détaille le **pourquoi** dans le corps si nécessaire.

## Documentation

Si ta PR ajoute une feature visible :

- Mets à jour le `README.md` (section "Récemment livré")
- Ajoute/modifie le doc concerné dans `docs/`
- Si c'est un nouveau service : crée `docs/<service>.md`
- Si c'est un nouveau skill : ajoute un exemple dans `docs/skills.md`

## Bonnes pratiques sécurité

- **Jamais de secrets en clair** dans le code ou les commits
- Utiliser des env vars + `.env.example` à jour
- Valider les inputs utilisateur côté gateway
- Pour reporter une vuln : voir [`SECURITY.md`](SECURITY.md)

## Reviews

Les maintainers (cf. [`CODEOWNERS`](../CODEOWNERS)) review dans les **3-5 jours**. Si pas de réponse :

1. Ping en commentaire (poliment)
2. Si toujours rien après 7 jours, ping sur les Discussions

Critères de merge :
- ✅ CI verte
- ✅ Tests qui couvrent le nouveau code
- ✅ Pas de regression visible
- ✅ Documentation à jour
- ✅ Au moins 1 approval

## Aide

- 💬 [GitHub Discussions](https://github.com/Micka420-collab/Jarvis3.0/discussions) — questions, idées, showcase
- 🐛 [Issues](https://github.com/Micka420-collab/Jarvis3.0/issues) — bugs, features
- 📖 [docs/](../docs/) — guides détaillés
- 🆘 [`SUPPORT.md`](SUPPORT.md) — où demander de l'aide

Merci pour ta contribution. 🚀
