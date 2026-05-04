"""Skill 'agents' : Jarvis délègue des tâches à des agents externes
(Hermes Agent NousResearch, OpenClaw, ou tout adapter MCP/CLI).

Cas d'usage :
    "Hermes, ouvre Chrome et trouve-moi un vol Paris→Tokyo le 12 août"
    "OpenClaw, classe mes derniers téléchargements par type dans le bon dossier"

Cette opération est gated `requires_admin` car les agents peuvent toucher
au PC de l'utilisateur (browser, fichiers, OS).
"""

from __future__ import annotations

import logging

import httpx

from .. import Skill

log = logging.getLogger("skills.agents")

AGENTS_URL = "http://agents:8005"


async def _list_agents(args: dict, ctx: dict) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{AGENTS_URL}/agents")
        return {"agents": r.json()}


async def _delegate(args: dict, ctx: dict) -> dict:
    agent = args.get("agent") or "hermes"
    goal = args.get("goal") or ""
    if not goal.strip():
        return {"error": "goal vide"}
    payload = {
        "agent": agent,
        "goal": goal,
        "user_id": ctx.get("user_id"),
        "context": {
            "session_id": ctx.get("session_id", ""),
            "is_owner": ctx.get("is_owner", False),
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{AGENTS_URL}/delegate", json=payload)
        if r.status_code != 200:
            return {"error": r.text, "status": r.status_code}
        return r.json()


async def _task_status(args: dict, ctx: dict) -> dict:
    task_id = args.get("task_id")
    if not task_id:
        return {"error": "task_id manquant"}
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{AGENTS_URL}/tasks/{task_id}")
        if r.status_code != 200:
            return {"error": r.text}
        return r.json()


async def _task_cancel(args: dict, ctx: dict) -> dict:
    task_id = args.get("task_id")
    if not task_id:
        return {"error": "task_id manquant"}
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(f"{AGENTS_URL}/tasks/{task_id}/cancel")
        return {"cancelled": r.status_code == 200}


def register(s: Skill) -> None:
    s.name = "agents"
    s.description = "Délégation de tâches à des agents externes (Hermes, OpenClaw)"
    s.tool(
        name="agent_list",
        description="Liste les agents externes disponibles et leur état.",
        input_schema={"type": "object", "properties": {}},
        handler=_list_agents,
    )
    s.tool(
        name="agent_delegate",
        description=(
            "Délègue une tâche autonome à un agent externe. "
            "L'agent peut interagir avec le PC : browser, fichiers, OS, GUI. "
            "Utilise 'hermes' pour les tâches de raisonnement / shell / coding ; "
            "'openclaw' pour les automations et les services en ligne (Gmail, GitHub, etc.)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Nom de l'agent : 'hermes' | 'openclaw' | 'mock'",
                },
                "goal": {
                    "type": "string",
                    "description": "Description claire de la tâche à accomplir.",
                },
            },
            "required": ["agent", "goal"],
        },
        handler=_delegate,
        requires_admin=True,
    )
    s.tool(
        name="agent_task_status",
        description="État d'une tâche déléguée à un agent (status, output, exit code).",
        input_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
        handler=_task_status,
    )
    s.tool(
        name="agent_task_cancel",
        description="Annule une tâche en cours (kill subprocess).",
        input_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
        handler=_task_cancel,
        requires_admin=True,
    )
