# Mémoire long-terme — v0.2

La mémoire de Jarvis combine **recherche vectorielle** (Qdrant + bge-m3 multilingue) et **recherche full-text BM25** (Postgres tsvector français) avec un **scoring composite** qui pondère similarité, récence, importance et utilisation.

## Vue d'ensemble

```
              ┌─────────────────────────┐
   /remember  │  service memory :8004    │
   /recall    │                          │
   /facts     │  ┌────────┐ ┌─────────┐ │
   /feedback  │  │ Qdrant │ │ Postgres│ │
   /forget    │  │vectors │ │ facts + │ │
   /stats ──▶ │  │  bge-m3│ │ tsvector│ │
              │  └────────┘ └─────────┘ │
              └─────────────────────────┘
```

## Pipeline d'ingestion (`POST /remember`)

```
  text utilisateur
     │
     ▼
  ┌─────────────────────────┐
  │ 1. Déduplication        │ pg_trgm similarity ≥ 0.92 → skip
  │ 2. Classification       │ heuristique → kind (preference/fact/event…)
  │ 3. Importance auto      │ kind + marqueurs ("important", "anniversaire")
  │ 4. Insert facts         │ Postgres + tsvector indexé full-text
  │ 5. Chunking             │ split phrases, target 600 chars, overlap 80
  │ 6. Embedding batch      │ bge-m3 (cache LRU 256 entrées)
  │ 7. Upsert Qdrant        │ payload {fact_id, user_id, kind, chunk_idx}
  └─────────────────────────┘
```

## Pipeline de recall (`GET /recall`)

```
  query utilisateur
     │
     ├──► Qdrant (vectoriel, k×4 candidats)  ──┐
     │                                         │
     ├──► Postgres BM25 (tsvector FR, k×4)  ───┤
     │                                         ▼
     │                            ┌────────────────────┐
     │                            │ Reciprocal Rank    │
     │                            │ Fusion (RRF, k=60) │
     │                            └────────────────────┘
     │                                         │
     │                                         ▼
     │                            ┌─────────────────────────┐
     │                            │ Re-scoring composite :   │
     │                            │  0.55 × similarity       │
     │                            │  0.20 × exp(-age/90j)    │
     │                            │  0.15 × importance       │
     │                            │  0.10 × log(use)         │
     │                            └─────────────────────────┘
     │                                         │
     │                                         ▼
     └──► Top-K finaux + record_recall (last_recalled_at, recall_count++)
```

## Catégories (`kind`)

| Kind | Description | Importance auto |
|---|---|---|
| `preference` | "j'aime", "je n'aime pas", "préfère" | 0.7 |
| `fact` | info objective ("habite à", "travaille chez") | 0.6 |
| `event` | passé daté ("hier", "la semaine dernière") | 0.4 |
| `skill_observation` | observation pour learning ("toujours à 19h") | 0.65 |
| `conversation` | dialogue ("a dit que") | 0.3 |
| `other` | reste | 0.5 |

Détection automatique si `kind` n'est pas fourni explicitement.

**Boost d'importance** automatique si le texte contient :
- `important`, `n'oublie pas`, `rappelle-toi`, `remember` → +0.20
- `anniversaire`, `naissance`, `mariage` → +0.15

## Endpoints

### `POST /remember`

```json
{
  "text": "J'aime le café noir le matin",
  "user_id": "uuid-optionnel",
  "tags": ["café", "préférence"],
  "kind": null,
  "importance": null,
  "source": "orchestrator",
  "deduplicate": true
}
```

Réponse :
```json
{
  "fact_id": "uuid",
  "chunks": 1,
  "kind": "preference",
  "importance": 0.7,
  "duplicate_of": null
}
```

### `GET /recall`

```bash
curl "http://localhost:8004/recall?query=ma%20voiture&k=5&hybrid=true&min_score=0.3"
```

Paramètres :
- `query` (str, requis)
- `k` (int, défaut 5)
- `user_id` (str, filtre)
- `kind` (str, filtre)
- `hybrid` (bool, défaut true) — active BM25 en plus du vectoriel
- `min_score` (float, défaut 0.0) — seuil composite [0..1]

### `GET /facts`, `GET /facts/{id}`, `PATCH /facts/{id}`, `DELETE /facts/{id}`

CRUD complet. Le PATCH ré-embed et re-upsert les chunks Qdrant si `text` change.

### `POST /feedback`

```json
{ "fact_id": "uuid", "helpful": true, "delta": 0.05 }
```

Boost l'importance de `±delta` (clamp [0,1]) et incrémente `recall_count` si `helpful=true`. Utilisé par le bouton "Pourquoi ?" / explain pour le feedback loop.

### `POST /forget`

```bash
curl -X POST "http://localhost:8004/forget?max_age_days=365&importance_max=0.4"
```

Supprime les faits :
- plus vieux que `max_age_days`
- ET `importance ≤ importance_max`
- ET `recall_count = 0`

Garde indéfiniment les souvenirs précieux ou rappelés au moins 1 fois.

### `GET /stats`

```json
{
  "total": 1234,
  "by_kind": [{"kind": "fact", "n": 600}, {"kind": "preference", "n": 320}, ...],
  "by_user": [{"user_id": "uuid", "n": 450}, ...],
  "avg_importance": 0.58,
  "most_recalled": [{"id": "...", "text": "...", "recall_count": 42}, ...],
  "qdrant_points": 3120,
  "embed_cache_size": 87
}
```

## Configuration

| Variable | Défaut | Effet |
|---|---|---|
| `EMBED_MODEL` | `BAAI/bge-m3` | Modèle d'embedding (multilingue, 1024-d) |
| `EMBED_CACHE_SIZE` | `256` | LRU cache pour les queries répétées |
| `QDRANT_COLLECTION` | `conversations` | Nom de la collection Qdrant |
| `MEM_W_SIM` | `0.55` | Poids similarité dans le score composite |
| `MEM_W_REC` | `0.20` | Poids récence |
| `MEM_W_IMP` | `0.15` | Poids importance |
| `MEM_W_USE` | `0.10` | Poids utilisation |
| `MEM_HALF_LIFE_DAYS` | `90` | Demi-vie de la décroissance temporelle |
| `MEM_MAX_RECALLS` | `20` | Saturation du log d'utilisation |

Les poids doivent sommer ~1.0 pour rester interprétables.

## Tools LLM (skill `memory`)

| Tool | Description | Admin ? |
|---|---|---|
| `memory_remember(text, tags?, kind?, importance?)` | Mémorise un fait | non |
| `memory_recall(query, k?, kind?, min_score?)` | Recherche hybride | non |
| `memory_forget(fact_id)` | Supprime un fait | **oui** |
| `memory_stats()` | Compteurs | non |

Le LLM peut alors décider de mémoriser ("Souviens-toi que…") ou récupérer ("Tu te rappelles…") sans intervention humaine. Le RAG automatique (`rag.py`) reste actif pour enrichir chaque tour.

## Migration v0.1 → v0.2

La table `facts` a 6 nouvelles colonnes : `kind`, `importance`, `tsv` (généré), `recall_count`, `last_recalled_at`, `source`, `updated_at`. L'`init.sql` les ajoute via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` donc c'est idempotent. Au premier start après mise à jour, les faits existants ont :
- `kind = 'fact'`
- `importance = 0.5`
- `recall_count = 0`
- `tsv` regénéré automatiquement

Aucune perte de données. Pour bénéficier des heuristiques (kind/importance auto), il faut soit ré-insérer les faits, soit les patcher individuellement.

## Performance

| Opération | Latence p50 | p95 |
|---|---|---|
| `POST /remember` (1 chunk) | ~80 ms | ~200 ms |
| `POST /remember` (5 chunks) | ~200 ms | ~500 ms |
| `GET /recall` (hybrid k=5) | ~100 ms | ~250 ms |
| `GET /recall` (cache hit) | ~20 ms | ~50 ms |
| `GET /stats` | ~30 ms | ~80 ms |

(Mesurées sur Pi 5 8GB, modèle bge-m3 quantized.)
