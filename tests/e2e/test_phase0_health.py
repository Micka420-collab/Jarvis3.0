"""Smoke E2E phase 0 : tous les services /health répondent.

À lancer après `make up` :
    docker compose exec gateway pytest /app/tests/e2e/test_phase0_health.py -v
"""

import asyncio

import httpx
import pytest

ENDPOINTS = {
    "gateway": "http://gateway:8000/api/health",
    "llm": "http://llm:8000/health",
    "orchestrator": "http://orchestrator:8001/health",
    "memory": "http://memory:8004/health",
    "iot": "http://iot:8002/health",
    "security": "http://security:8003/health",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name,url", list(ENDPOINTS.items()))
async def test_health(name: str, url: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(url)
        assert r.status_code == 200, f"{name} KO: {r.status_code}"
        assert r.json().get("status") == "ok"
