"""Skill 'memory' : expose remember / recall / forget au LLM.

Le LLM peut décider de mémoriser un fait quand l'utilisateur dit explicitement
quelque chose comme :
  "Souviens-toi que j'aime le café noir"
  "N'oublie pas mon anniversaire le 14 mars"
  "Mémorise : ma voiture est garée place 42 niveau B2"

Ou de récupérer un souvenir avant de répondre :
  "Tu te rappelles où j'ai garé ma voiture ?"
  "Quels sont mes plats préférés ?"

Le RAG automatique (rag.py) est différent : il enrichit chaque tour avec
les top-K souvenirs sans demander au LLM. Ce skill permet au LLM de
*explicitement* mémoriser ou de chercher ciblément.
"""

from __future__ import annotations

import logging
import os

import httpx

from .. import Skill

log = logging.getLogger("skills.memory")

MEMORY_URL = os.getenv("MEMORY_URL", "http://memory:8004")


async def _remember(args: dict, ctx: dict) -> dict:
    text = (args.get("text") or "").strip()
    if not text:
        return {"error": "text vide"}
    body = {
        "text": text,
        "user_id": ctx.get("user_id"),
        "tags": args.get("tags") or [],
        "kind": args.get("kind"),
        "importance": args.get("importance"),
        "source": "orchestrator",
    }
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(f"{MEMORY_URL}/remember", json=body)
        if r.status_code != 200:
            return {"error": r.text[:200]}
        return r.json()


async def _recall(args: dict, ctx: dict) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "query vide"}
    params: dict = {
        "query": query,
        "k": int(args.get("k", 5)),
        "user_id": ctx.get("user_id") or "",
        "kind": args.get("kind") or "",
        "hybrid": "true",
        "min_score": float(args.get("min_score", 0.0)),
    }
    async with httpx.AsyncClient(timeout=3.0) as c:
        r = await c.get(f"{MEMORY_URL}/recall", params=params)
        if r.status_code != 200:
            return {"error": r.text[:200]}
        return r.json()


async def _forget_fact(args: dict, ctx: dict) -> dict:
    fact_id = args.get("fact_id")
    if not fact_id:
        return {"error": "fact_id manquant"}
    async with httpx.AsyncClient(timeout=3.0) as c:
        r = await c.delete(f"{MEMORY_URL}/facts/{fact_id}")
        if r.status_code == 404:
            return {"error": "fact inconnu"}
        return r.json()


async def _memory_stats(args: dict, ctx: dict) -> dict:
    async with httpx.AsyncClient(timeout=3.0) as c:
        r = await c.get(f"{MEMORY_URL}/stats")
        return r.json() if r.status_code == 200 else {"error": r.text[:200]}


def register(s: Skill) -> None:
    s.name = "memory"
    s.description = "Mémoire long-terme : remember, recall, forget"

    s.tool(
        name="memory_remember",
        description=(
            "Mémorise un fait, une préférence ou un événement durablement. "
            "À utiliser quand l'utilisateur demande explicitement de retenir "
            "(ex: 'souviens-toi que…', 'n'oublie pas…', 'mémorise…')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Texte à retenir, formulé clairement à la 3e personne si possible.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags optionnels (ex: 'voiture', 'cuisine', 'anniversaire').",
                },
                "kind": {
                    "type": "string",
                    "enum": ["preference", "fact", "event", "skill_observation", "conversation", "other"],
                    "description": "Catégorie. Auto-détectée si omise.",
                },
                "importance": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Importance subjective. Auto-calculée si omise.",
                },
            },
            "required": ["text"],
        },
        handler=_remember,
    )

    s.tool(
        name="memory_recall",
        description=(
            "Recherche dans la mémoire long-terme. Hybride vectoriel + BM25 + "
            "scoring composite (similarité + récence + importance + utilisation)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question / mot-clé"},
                "k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                "kind": {
                    "type": "string",
                    "enum": ["preference", "fact", "event", "skill_observation", "conversation", "other"],
                    "description": "Filtrer par catégorie.",
                },
                "min_score": {"type": "number", "default": 0.3},
            },
            "required": ["query"],
        },
        handler=_recall,
    )

    s.tool(
        name="memory_forget",
        description="Supprime définitivement un fait. Demander confirmation avant.",
        input_schema={
            "type": "object",
            "properties": {"fact_id": {"type": "string"}},
            "required": ["fact_id"],
        },
        handler=_forget_fact,
        requires_admin=True,
    )

    s.tool(
        name="memory_stats",
        description="Statistiques mémoire (total, par catégorie, par utilisateur, top rappelés).",
        input_schema={"type": "object", "properties": {}},
        handler=_memory_stats,
    )
