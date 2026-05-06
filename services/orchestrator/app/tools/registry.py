"""Définit les tools (Anthropic schema) et dispatch les appels."""

from __future__ import annotations

from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Schémas (compatibles Anthropic + Mistral function calling)
# ---------------------------------------------------------------------------

TOOL_DEFS: list[dict] = [
    {
        "name": "iot_command",
        "description": "Pilote un appareil (lumière, volet, prise, porte). requires_admin pour les actions sensibles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "action": {"type": "string", "enum": ["on", "off", "toggle", "open", "close", "set"]},
                "params": {"type": "object"},
            },
            "required": ["device_id", "action"],
        },
    },
    {
        "name": "iot_state",
        "description": "Consulte l'état actuel d'un appareil.",
        "input_schema": {
            "type": "object",
            "properties": {"device_id": {"type": "string"}},
            "required": ["device_id"],
        },
    },
    {
        "name": "memory_remember",
        "description": "Mémorise un fait long-terme à propos de l'utilisateur.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
        },
    },
    {
        "name": "memory_recall",
        "description": "Recherche dans la mémoire long-terme.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
            "required": ["query"],
        },
    },
    {
        "name": "security_status",
        "description": "Renvoie l'état d'Argus (alertes récentes, sévérité).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "security_silence",
        "description": "Suspend les annonces vocales d'alertes Argus pendant N minutes. Owner uniquement.",
        "input_schema": {
            "type": "object",
            "properties": {"minutes": {"type": "integer"}},
            "required": ["minutes"],
        },
    },
]

ADMIN_TOOLS = {"security_silence"}


async def dispatch_tool(name: str, arguments: dict, user_id: str | None, is_owner: bool) -> dict[str, Any]:
    if name in ADMIN_TOOLS and not is_owner:
        return {"error": "owner only"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        if name == "iot_command":
            r = await client.post("http://iot:8002/command", json=arguments)
            return r.json()
        if name == "iot_state":
            r = await client.get("http://iot:8002/state", params=arguments)
            return r.json()
        if name == "memory_remember":
            r = await client.post(
                "http://memory:8004/remember",
                json={**arguments, "user_id": user_id},
            )
            return r.json()
        if name == "memory_recall":
            r = await client.get(
                "http://memory:8004/recall",
                params={**arguments, "user_id": user_id or ""},
            )
            return r.json()
        if name == "security_status":
            r = await client.get("http://security:8003/status")
            return r.json()
        if name == "security_silence":
            r = await client.post(
                "http://security:8003/silence",
                json={"duration_minutes": arguments.get("minutes", 30)},
            )
            return r.json()
    return {"error": f"tool inconnu: {name}"}
