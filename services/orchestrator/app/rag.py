"""Memory-augmented prompting (RAG sur la mémoire long-terme).

Avant chaque tour, on fait une recherche vectorielle Qdrant sur les souvenirs
pertinents pour le `user_text` courant, et on les injecte dans le prompt
système comme contexte.

Latence ajoutée : ~30-80 ms (1 appel HTTP au service memory). Si timeout ou
erreur, on continue sans RAG.
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


async def fetch_relevant_memories(query: str, user_id: str | None = None) -> list[dict]:
    """Renvoie jusqu'à K souvenirs pertinents au-dessus du seuil de similarité."""
    if not query.strip():
        return []
    params = {"query": query, "k": RAG_K, "user_id": user_id or ""}
    try:
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
            r = await client.get(f"{MEMORY_URL}/recall", params=params)
            if r.status_code != 200:
                return []
            data = r.json()
        hits = data.get("results", [])
        return [h for h in hits if h.get("score", 0) >= RAG_MIN_SCORE]
    except Exception as e:
        log.debug("RAG fetch failed (%s) — fallback no-memory", e)
        return []


def format_context(memories: list[dict]) -> str:
    """Formate les souvenirs pour les injecter dans le prompt système."""
    if not memories:
        return ""
    lines = ["", "## Souvenirs pertinents (top-K)"]
    for m in memories:
        text = m.get("text", "").strip()
        score = m.get("score", 0)
        if text:
            lines.append(f"- [{score:.2f}] {text}")
    return "\n".join(lines)
