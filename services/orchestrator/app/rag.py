"""Memory-augmented prompting (RAG sur la mémoire long-terme).

Avant chaque tour, on fait une recherche hybride (vectoriel + BM25 + scoring
composite) sur les souvenirs pertinents et on les injecte dans le prompt
système comme contexte.

Améliorations vs v0.1 :
- `hybrid=true` côté memory v0.2 (BM25 + vector via RRF)
- Filtrage min_score côté serveur (gain latence : moins de payload)
- Filtre par kind (preference, fact, event…) si fourni
- Format inclut le kind pour que le LLM sache si c'est une préférence,
  un fait objectif ou un événement passé

Latence ajoutée : ~50-150 ms (1 appel HTTP au service memory). Timeout =
fallback no-memory.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("orchestrator.rag")

MEMORY_URL = os.getenv("MEMORY_URL", "http://memory:8004")
RAG_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.55"))
RAG_TIMEOUT_S = float(os.getenv("RAG_TIMEOUT_S", "1.5"))


async def fetch_relevant_memories(
    query: str,
    *,
    user_id: str | None = None,
    kind: str | None = None,
) -> list[dict]:
    """Renvoie jusqu'à K souvenirs pertinents au-dessus du seuil min_score.

    Le service memory v0.2 gère le scoring composite et le min_score
    côté serveur, on transmet juste les paramètres.
    """
    if not query.strip():
        return []
    params: dict[str, str | int | float] = {
        "query": query,
        "k": RAG_K,
        "user_id": user_id or "",
        "kind": kind or "",
        "hybrid": "true",
        "min_score": RAG_MIN_SCORE,
    }
    try:
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
            r = await client.get(f"{MEMORY_URL}/recall", params=params)
            if r.status_code != 200:
                log.debug("RAG %d : %s", r.status_code, r.text[:200])
                return []
            data = r.json()
        return data.get("results", [])
    except Exception as e:
        log.debug("RAG fetch failed (%s) — fallback no-memory", e)
        return []


def format_context(memories: list[dict]) -> str:
    """Formate les souvenirs pour les injecter dans le prompt système.

    Inclut le kind pour que le LLM comprenne le statut de chaque souvenir
    (préférence > fait > événement passé > observation).
    """
    if not memories:
        return ""
    lines = ["", "## Souvenirs pertinents (top-K)"]
    for m in memories:
        text = (m.get("text") or "").strip()
        score = m.get("score", 0)
        kind = m.get("kind", "fact")
        if text:
            lines.append(f"- [{kind} · {score:.2f}] {text}")
    return "\n".join(lines)


async def send_feedback(fact_id: str, *, helpful: bool = True) -> None:
    """Signale au service memory qu'un recall a été utile (boost importance)
    ou pas (down). Appelé par le bouton "Pourquoi ?" / explain.
    """
    if not fact_id:
        return
    try:
        async with httpx.AsyncClient(timeout=1.0) as c:
            await c.post(
                f"{MEMORY_URL}/feedback",
                json={"fact_id": fact_id, "helpful": helpful},
            )
    except Exception as e:
        log.debug("feedback failed (%s)", e)
